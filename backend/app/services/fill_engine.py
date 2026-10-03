"""Vending refill: gap = capacity - stock - in_transit; fills capped by gap; no negative fills.

三态口径互斥，以库存加在途与容量的关系唯一判定：
- overbooked（超占）: stock + in_transit > capacity，gap < 0，补量只能为 0；
- full（满仓）     : stock + in_transit == capacity，gap == 0，补量为 0；
- need_fill（待补）: stock + in_transit < capacity，gap > 0，补量不超过 gap。
超占与满仓互斥：超占货道不得进入满仓名单，超占原因也不得与满仓文案并句。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked
    reason: str  # 状态原因，超占与满仓各自独立成句

def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit

def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane_id; capped by gap; never negative."""
    lines: list[FillLine] = []
    for lane in lanes:
        capacity, stock, in_transit = int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"])
        gap = compute_gap(capacity, stock, in_transit)
        occupied = stock + in_transit
        if occupied > capacity:
            # 库存加在途大于容量：只能是超占，补量强制为 0，原因独立成句
            status = "overbooked"
            fill = 0
            reason = f"超占：库存 {stock} 加在途 {in_transit} 共 {occupied}，大于容量 {capacity}，本次补量为 0"
        elif occupied == capacity:
            status = "full"
            fill = 0
            reason = "满仓：库存加在途正好等于容量，缺口为 0，无需补货"
        else:
            status = "need_fill"
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
            reason = f"待补：缺口 {gap}"
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=capacity, stock=stock, in_transit=in_transit,
            gap=gap, fill_qty=fill, status=status, reason=reason,
        ))
    return lines

def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "lines": [asdict(l) for l in lines],
    }
