"""补货单快照服务。

关键不变量：货道现态、最新补货单的行状态、满仓名单、汇总计数共用同一份
fill_engine 口径，并且货道改数与“最新补货单回写”必须在同一事务里提交，
做到同一次保存一起跳变。更早的历史单据永不回刷。
"""
from __future__ import annotations
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


def lanes_payload(db: Session, location_id: int) -> list[dict]:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
             "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit}
            for l in lanes]


def compute_summary(db: Session, location_id: int) -> dict:
    """按当前货道现态重算整单（行状态/补量/计数），口径全部来自 fill_engine。"""
    return summarize(build_fill_lines(lanes_payload(db, location_id)))


def sync_latest_order(db: Session, location_id: int) -> RefillOrder:
    """把当前货道现态写回“最新一张补货单”。

    必须在调用方的事务内调用（与货道 UPDATE 同一事务提交）。
    已有最新单则原地重算其 lines_json；没有则新建一张。
    只动最新单，历史非最新单一律不回刷。
    """
    summary = compute_summary(db, location_id)
    order = db.scalars(
        select(RefillOrder).where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).first()
    if order is None:
        order = RefillOrder(location_id=location_id, created_at=datetime.utcnow())
        db.add(order)
        db.flush()  # 取 order.id
    order.lines_json = json.dumps(summary, ensure_ascii=False)
    return order


def order_payload(order: RefillOrder, location_id: int) -> dict:
    data = json.loads(order.lines_json)
    return {"id": order.id, "location_id": location_id, **data}
