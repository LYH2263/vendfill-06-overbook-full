from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import compute_gap, lane_status
from app.services.refill_service import order_payload, sync_latest_order
router = APIRouter(prefix="/lanes", tags=["lanes"])

@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None: q = q.where(Lane.location_id == location_id)
    out = []
    for r in db.scalars(q).all():
        gap = compute_gap(r.capacity, r.stock, r.in_transit)
        out.append({"id": r.id, "location_id": r.location_id, "slot_no": r.slot_no, "sku_name": r.sku_name,
                    "capacity": r.capacity, "stock": r.stock, "in_transit": r.in_transit, "gap": gap,
                    "status": lane_status(gap),
                    "fill_pct": round(r.stock / r.capacity * 100, 1) if r.capacity else 0})
    return out


class LaneQty(BaseModel):
    id: int
    stock: int = Field(ge=0)
    in_transit: int = Field(ge=0)


class SaveLanes(BaseModel):
    location_id: int = 1
    lanes: list[LaneQty]


@router.put("")
def save_lanes(payload: SaveLanes, db: Session = Depends(get_db)):
    """保存货道库存/在途，并在同一事务内让最新补货单的行状态、满仓名单、
    汇总计数与货道现态一起跳变。只回写最新单，历史单据保持生成当时的字。"""
    rows = {r.id: r for r in db.scalars(
        select(Lane).where(Lane.location_id == payload.location_id)).all()}
    if not rows:
        raise HTTPException(404, "点位不存在或无货道")
    for item in payload.lanes:
        lane = rows.get(item.id)
        if lane is None:
            raise HTTPException(404, f"货道 {item.id} 不属于该点位")
        lane.stock = item.stock
        lane.in_transit = item.in_transit
    db.flush()  # 让同事务内的重算读到新货道值；与下面单据回写共用最后一次 commit
    # 货道 UPDATE 与最新单回写同一事务、一次 commit：任一方失败整场不落库。
    order = sync_latest_order(db, payload.location_id)
    db.commit(); db.refresh(order)
    return order_payload(order, payload.location_id)
