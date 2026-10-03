import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Lane, RefillOrder
from app.services.seed import seed_if_empty


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    seed_if_empty(db)  # C2: 容量24/库存24/在途2 -> 超占
    db.close()

    def _get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def _line(order, slot):
    return next(l for l in order["lines"] if l["slot_no"] == slot)


def _historical(Session, order_id):
    db = Session()
    raw = db.scalars(select(RefillOrder).where(RefillOrder.id == order_id)).one().lines_json
    db.close()
    return json.loads(raw)


# ---- 种子 C2 超占时：满仓页无 C2；超占原因不与满仓并句 ----

def test_seed_c2_overbooked_not_on_full_page(client):
    c, _ = client
    full = c.get("/api/refills/full?location_id=1").json()
    slots = {l["slot_no"] for l in full["lanes"]}
    assert "C2" not in slots                       # 满仓页禁止混入超占
    assert {"A2", "B2"} <= slots                  # 真正满仓的仍在
    s = c.get("/api/refills/summary?location_id=1").json()
    assert s["overbooked_count"] == 1
    assert s["full_count"] == 2
    latest = c.get("/api/refills/latest?location_id=1").json()
    c2 = _line(latest, "C2")
    assert c2["status"] == "overbooked" and c2["fill_qty"] == 0


# ---- 改在途离开超占：行状态/满仓名单/汇总同一跳变；历史单不回刷 ----

def test_leave_overbooked_syncs_together_history_untouched(client):
    c, Session = client
    # 连续造两张单（#1 历史、#2 最新），均生成于 C2 超占当时
    first = c.post("/api/refills/run?location_id=1").json()
    second = c.post("/api/refills/run?location_id=1").json()
    assert first["id"] != second["id"]
    hist_c2 = next(l for l in _historical(Session, first["id"])["lines"] if l["slot_no"] == "C2")
    assert hist_c2["status"] == "overbooked"

    db = Session()
    c2_id = db.scalars(select(Lane).where(Lane.slot_no == "C2")).one().id
    db.close()

    # 把 C2 在途 2 -> 0：库存+在途=容量=24，恰好满仓
    put = c.put("/api/lanes?location_id=1", json={
        "location_id": 1,
        "lanes": [{"id": c2_id, "stock": 24, "in_transit": 0}],
    }).json()
    assert _line(put, "C2")["status"] == "full"
    assert _line(put, "C2")["fill_qty"] == 0

    latest = c.get("/api/refills/latest?location_id=1").json()
    assert _line(latest, "C2")["status"] == "full"          # 最新单行跟上
    full = c.get("/api/refills/full?location_id=1").json()
    assert "C2" in {l["slot_no"] for l in full["lanes"]}    # 满仓名单跟上
    s = c.get("/api/refills/summary?location_id=1").json()
    assert s["overbooked_count"] == 0                       # 汇总一起离开超占口径
    assert s["full_count"] == 3

    # 历史非最新单行仍保持生成当时的字，不被这次改数回刷
    old = _historical(Session, first["id"])
    old_c2 = next(l for l in old["lines"] if l["slot_no"] == "C2")
    assert old_c2["status"] == "overbooked"
    assert old_c2["in_transit"] == 2


# ---- 再改回超占：四处同一跳变回来，仍不新增单、不刷历史 ----

def test_reenter_overbooked_syncs_together(client):
    c, Session = client
    db = Session()
    c2_id = db.scalars(select(Lane).where(Lane.slot_no == "C2")).one().id
    db.close()
    before = c.get("/api/refills/latest?location_id=1").json()

    c.put("/api/lanes?location_id=1", json={
        "location_id": 1, "lanes": [{"id": c2_id, "stock": 24, "in_transit": 0}],
    })
    back = c.put("/api/lanes?location_id=1", json={
        "location_id": 1, "lanes": [{"id": c2_id, "stock": 24, "in_transit": 2}],
    }).json()

    assert back["id"] == before["id"]                       # 回写最新单，而非乱建单
    assert _line(back, "C2")["status"] == "overbooked"
    assert _line(back, "C2")["fill_qty"] == 0
    full = c.get("/api/refills/full?location_id=1").json()
    assert "C2" not in {l["slot_no"] for l in full["lanes"]}
    s = c.get("/api/refills/summary?location_id=1").json()
    assert s["overbooked_count"] == 1 and s["full_count"] == 2


# ---- 未超占时与现网一致：补量=缺口，部分保存不影响其他货道 ----

def test_non_overbooked_matches_live_and_partial_save(client):
    c, _ = client
    db_payload = c.get("/api/lanes?location_id=1").json()
    a1 = next(r for r in db_payload if r["slot_no"] == "A1")
    latest = c.get("/api/refills/latest?location_id=1").json()
    assert _line(latest, "A1")["fill_qty"] == a1["gap"] == 15
    assert _line(latest, "B1")["fill_qty"] == 7

    # 只保存 C2 一行，其他货道现态必须保持
    c.put("/api/lanes?location_id=1", json={
        "location_id": 1, "lanes": [{"id": a1["id"], "stock": 5, "in_transit": 0}],
    })
    rows = {r["slot_no"]: r for r in c.get("/api/lanes?location_id=1").json()}
    assert rows["B1"]["stock"] == 3 and rows["B1"]["in_transit"] == 2
    assert rows["A2"]["stock"] == 18 and rows["A2"]["in_transit"] == 0
