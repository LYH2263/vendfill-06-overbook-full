"""Vending refill.

口径（唯一事实源，所有展示/单据/名单/计数共用）：
  stock + in_transit >  capacity  -> overbooked 超占，补量恒为 0
  stock + in_transit == capacity  -> full 满仓，补量为 0
  stock + in_transit <  capacity  -> need_fill，补量为 [0, gap] 内的值

“超占”与“满仓”互斥：超占只能由 stock+in_transit>capacity 单独表达，
任何名单/句子都不得把超占原因与满仓并句。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

STATUS_NEED_FILL = "need_fill"
STATUS_FULL = "full"
STATUS_OVERBOOKED = "overbooked"

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

def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit

def lane_status(gap: int) -> str:
    """同一跳变口径：超占与满仓互斥，超占只由 gap<0 表达。"""
    if gap < 0:
        return STATUS_OVERBOOKED
    if gap == 0:
        return STATUS_FULL
    return STATUS_NEED_FILL

def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane; 超占/满仓时强制补量 0；其余以 gap 封顶，非负。"""
    lines: list[FillLine] = []
    for lane in lanes:
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        status = lane_status(gap)
        if status != STATUS_NEED_FILL:
            # 超占或满仓：补量只能是 0；超占时 gap 为负，绝不允许正补量。
            fill = 0
        else:
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status,
        ))
    return lines

def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == STATUS_NEED_FILL),
        "full_count": sum(1 for l in lines if l.status == STATUS_FULL),
        "overbooked_count": sum(1 for l in lines if l.status == STATUS_OVERBOOKED),
        "lines": [asdict(l) for l in lines],
    }
