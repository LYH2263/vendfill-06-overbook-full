from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import build_fill_lines
from app.services.refill_orders import refresh_latest_order

router = APIRouter(prefix="/lanes", tags=["lanes"])


class LanePatch(BaseModel):
    stock: int | None = None
    in_transit: int | None = None


def _lanes_with_status(db: Session, location_id: int | None) -> list[dict]:
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None:
        q = q.where(Lane.location_id == location_id)
    rows = db.scalars(q).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in rows]
    status_by_id = {l.lane_id: l for l in build_fill_lines(payload)}
    out = []
    for r in rows:
        line = status_by_id[r.id]
        out.append({"id": r.id, "location_id": r.location_id, "slot_no": r.slot_no, "sku_name": r.sku_name,
                    "capacity": r.capacity, "stock": r.stock, "in_transit": r.in_transit,
                    "gap": line.gap, "fill_qty": line.fill_qty, "status": line.status, "reason": line.reason,
                    "fill_pct": round(r.stock / r.capacity * 100, 1) if r.capacity else 0})
    return out


@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    return _lanes_with_status(db, location_id)


@router.patch("/{lane_id}")
def update_lane(lane_id: int, patch: LanePatch, db: Session = Depends(get_db)):
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(404, "货道不存在")
    if patch.stock is not None:
        if patch.stock < 0:
            raise HTTPException(400, "库存不能为负")
        lane.stock = patch.stock
    if patch.in_transit is not None:
        if patch.in_transit < 0:
            raise HTTPException(400, "在途不能为负")
        lane.in_transit = patch.in_transit

    # 同一事务：货道改数 flush 后立即按现态重算并覆盖最新补货单，
    # 一次 commit 让货道现态、最新单行、满仓名单、汇总计数同时跳变；
    # 更早的历史单不在重算范围内，保持生成当时的状态。
    db.flush()
    order, summary = refresh_latest_order(db, lane.location_id)
    db.commit()

    db.refresh(lane)
    lanes = _lanes_with_status(db, lane.location_id)
    current = next(l for l in lanes if l["id"] == lane_id)
    return {"lane": current, "order_id": order.id, "location_id": lane.location_id, **summary}
