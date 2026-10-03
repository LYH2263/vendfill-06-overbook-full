from app.services.fill_engine import (
    build_fill_lines, compute_gap, lane_status, summarize,
    STATUS_FULL, STATUS_NEED_FILL, STATUS_OVERBOOKED,
)

def _lane(cap=10, stock=0, transit=0, lid=1):
    return {"id": lid, "slot_no": "A1", "sku_name": "水",
            "capacity": cap, "stock": stock, "in_transit": transit}

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lines = build_fill_lines([_lane(cap=10, stock=12, transit=0)])
    assert lines[0].fill_qty == 0
    assert lines[0].status == STATUS_OVERBOOKED

def test_in_transit_overbooked_forces_zero_fill():
    # 库存本身不超，但库存+在途超过容量：只能是超占，补量必须为 0
    lines = build_fill_lines([_lane(cap=10, stock=5, transit=6)])
    assert lines[0].gap == -1
    assert lines[0].status == STATUS_OVERBOOKED
    assert lines[0].fill_qty == 0

def test_overbooked_requested_quantity_still_zero():
    # 即使带了期望补量，超占行补量也只能是 0
    lines = build_fill_lines([_lane(cap=10, stock=9, transit=5)], requested={1: 100})
    assert lines[0].status == STATUS_OVERBOOKED
    assert lines[0].fill_qty == 0

def test_statuses_are_mutually_exclusive():
    assert lane_status(compute_gap(10, 5, 6)) == STATUS_OVERBOOKED  # 11 > 10
    assert lane_status(compute_gap(10, 8, 2)) == STATUS_FULL         # 10 == 10
    assert lane_status(compute_gap(10, 8, 1)) == STATUS_NEED_FILL    # 9 < 10

def test_cap_by_gap():
    lines = build_fill_lines([_lane(cap=20, stock=5, transit=0)], requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    s = summarize(build_fill_lines([_lane(cap=10, stock=8, transit=2)]))
    assert s["full_count"] == 1
    assert s["overbooked_count"] == 0
    assert s["total_fill"] == 0

def test_full_list_excludes_overbooked():
    # 满仓名单（status == full）不得混入超占
    lanes = [_lane(cap=10, stock=8, transit=2, lid=1),   # full
             _lane(cap=10, stock=9, transit=5, lid=2),   # overbooked
             _lane(cap=10, stock=4, transit=0, lid=3)]   # need_fill
    s = summarize(build_fill_lines(lanes))
    full = [l for l in s["lines"] if l["status"] == "full"]
    over = [l for l in s["lines"] if l["status"] == "overbooked"]
    assert [l["lane_id"] for l in full] == [1]
    assert [l["lane_id"] for l in over] == [2]
    assert s["full_count"] == 1 and s["overbooked_count"] == 1
