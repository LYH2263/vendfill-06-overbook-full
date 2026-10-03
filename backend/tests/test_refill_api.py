import json

from app.models.models import RefillOrder

# 种子货道按 slot 顺序落库：A1=1 A2=2 B1=3 B2=4 C1=5 C2=6
C2_ID = 6


def _line(data, lane_id):
    return next(l for l in data["lines"] if l["lane_id"] == lane_id)


def test_seed_c2_is_overbooked_and_excluded_from_full_page(client):
    lanes = {l["slot_no"]: l for l in client.get("/api/lanes").json()}
    c2 = lanes["C2"]
    assert c2["status"] == "overbooked"
    assert c2["gap"] == -2
    assert c2["fill_qty"] == 0
    assert "超占" in c2["reason"] and "满仓" not in c2["reason"]

    run = client.post("/api/refills/run").json()
    assert _line(run, C2_ID)["status"] == "overbooked"
    assert _line(run, C2_ID)["fill_qty"] == 0

    full = client.get("/api/refills/full").json()["lanes"]
    assert "C2" not in [l["slot_no"] for l in full]
    assert all(l["status"] == "full" for l in full)
    assert {l["slot_no"] for l in full} == {"A2", "B2"}

    s = client.get("/api/refills/summary").json()
    assert s["overbooked_count"] == 1
    assert s["full_count"] == 2
    assert s["need_fill_count"] == 3


def test_patch_leaves_overbooked_atomically_within_one_save(client, db_session):
    # 先留两张历史单：#1 与 #2 生成时 C2 均为超占
    first = client.post("/api/refills/run").json()
    second = client.post("/api/refills/run").json()
    assert first["id"] == 1 and second["id"] == 2
    assert _line(second, C2_ID)["status"] == "overbooked"

    # 同一次保存：PATCH 响应里货道现态、最新单行、满仓名单所需状态、汇总计数同时跳变
    resp = client.patch(f"/api/lanes/{C2_ID}", json={"in_transit": 0}).json()
    assert resp["order_id"] == 2
    assert resp["lane"]["status"] == "full"
    assert resp["lane"]["gap"] == 0
    assert resp["lane"]["in_transit"] == 0
    assert _line(resp, C2_ID)["status"] == "full"
    assert _line(resp, C2_ID)["reason"].count("满仓") == 1 and "超占" not in _line(resp, C2_ID)["reason"]
    assert resp["full_count"] == 3
    assert resp["overbooked_count"] == 0

    # 保存之后立刻独立查询：最新单、满仓名单、汇总全部跟上，不允许只改一头
    latest = client.get("/api/refills/latest").json()
    assert latest["id"] == 2
    assert _line(latest, C2_ID)["status"] == "full"

    full_slots = [l["slot_no"] for l in client.get("/api/refills/full").json()["lanes"]]
    assert "C2" in full_slots
    s = client.get("/api/refills/summary").json()
    assert s["overbooked_count"] == 0 and s["full_count"] == 3

    # 历史非最新单（#1）必须保持生成当时的字，不被这次改数回刷
    old = db_session.get(RefillOrder, 1)
    old_c2 = _line(json.loads(old.lines_json), C2_ID)
    assert old_c2["status"] == "overbooked"
    assert "超占" in old_c2["reason"]


def test_patch_back_into_overbooked_forces_zero_fill(client):
    client.post("/api/refills/run")
    client.patch(f"/api/lanes/{C2_ID}", json={"in_transit": 0})
    back = client.patch(f"/api/lanes/{C2_ID}", json={"in_transit": 2}).json()

    assert back["lane"]["status"] == "overbooked"
    assert _line(back, C2_ID)["fill_qty"] == 0
    assert back["overbooked_count"] == 1
    assert back["full_count"] == 2

    full_slots = [l["slot_no"] for l in client.get("/api/refills/full").json()["lanes"]]
    assert "C2" not in full_slots


def test_full_page_never_mixes_overbooked_after_stock_edit(client):
    client.post("/api/refills/run")
    # 把 A2 从满仓改成超占（库存 + 在途 > 容量）
    a2 = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "A2")
    client.patch(f"/api/lanes/{a2['id']}", json={"stock": a2["capacity"] + 3})
    full = client.get("/api/refills/full").json()["lanes"]
    assert all(l["status"] == "full" for l in full)
    assert "A2" not in [l["slot_no"] for l in full]
    assert client.get("/api/refills/summary").json()["overbooked_count"] == 2


def test_negative_numbers_rejected(client):
    assert client.patch(f"/api/lanes/{C2_ID}", json={"stock": -1}).status_code == 400
    assert client.patch(f"/api/lanes/{C2_ID}", json={"in_transit": -1}).status_code == 400
