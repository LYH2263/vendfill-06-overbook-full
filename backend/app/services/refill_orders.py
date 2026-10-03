"""补货单落库与重算。

货道改数与最新补货单重算必须在同一事务、同一提交内完成，
保证货道现态、最新单对应行状态、满仓名单、汇总计数同一跳变。
历史（非最新）补货单一旦生成即冻结，不得被后续改数回刷。
"""
from __future__ import annotations
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


def _lane_payload(lanes: list[Lane]) -> list[dict]:
    return [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
             "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]


def snapshot_location(db: Session, location_id: int) -> dict:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return summarize(build_fill_lines(_lane_payload(lanes)))


def _latest_order(db: Session, location_id: int) -> RefillOrder | None:
    return db.scalars(
        select(RefillOrder).where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).first()


def create_refill_order(db: Session, location_id: int) -> tuple[RefillOrder, dict]:
    """生成一张新补货单并落库（调用方负责提交）。"""
    summary = snapshot_location(db, location_id)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order)
    db.flush()
    return order, summary


def get_or_create_latest(db: Session, location_id: int) -> tuple[RefillOrder, dict]:
    order = _latest_order(db, location_id)
    if order is None:
        order, _summary = create_refill_order(db, location_id)
        db.commit()
        db.refresh(order)
    return order, json.loads(order.lines_json)


def refresh_latest_order(db: Session, location_id: int) -> tuple[RefillOrder, dict]:
    """按当前货道现态重算并【覆盖最新一张补货单】；没有则新建。

    必须在货道改数的同一事务内调用：只 flush 不 commit，由调用方一次提交，
    从而货道数字与最新单行状态原子跳变。更早的历史单一律不触碰。
    """
    summary = snapshot_location(db, location_id)
    order = _latest_order(db, location_id)
    if order is None:
        order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(), lines_json="")
        db.add(order)
        db.flush()
    order.lines_json = json.dumps(summary, ensure_ascii=False)
    db.flush()
    return order, summary
