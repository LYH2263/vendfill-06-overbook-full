import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Location, RefillOrder
from app.services.refill_service import compute_summary, order_payload, sync_latest_order
router = APIRouter(prefix="/refills", tags=["refills"])

@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    """显式生成一张新补货单（历史单据保留生成当时的字，不被后续改数回刷）。"""
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    summary = compute_summary(db, location_id)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return order_payload(order, location_id)

@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                       .order_by(RefillOrder.id.desc())).first()
    if not order:
        # 与现网一致：尚无单据时按当前现态落一张初始单。
        order = sync_latest_order(db, location_id)
        db.commit(); db.refresh(order)
    return order_payload(order, location_id)

@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    # 满仓名单只列 status == full；超占（overbooked）严禁混入。
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
    }
