from app.services.fill_engine import build_fill_lines, compute_gap, summarize

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 12, "in_transit": 0}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"

def test_cap_by_gap():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}]
    lines = build_fill_lines(lanes, requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 8, "in_transit": 2}]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0

def test_overbooked_when_stock_plus_transit_exceeds_capacity():
    # 库存未超容量，但库存加在途大于容量：只能是超占，补量必须为 0
    lanes = [{"id": 1, "slot_no": "C2", "sku_name": "口香糖", "capacity": 24, "stock": 24, "in_transit": 2}]
    lines = build_fill_lines(lanes)
    assert lines[0].gap == -2
    assert lines[0].status == "overbooked"
    assert lines[0].fill_qty == 0

def test_full_is_exactly_at_capacity_boundary():
    # 等于容量是满仓，减一离开满仓变待补，加一进入超占
    base = {"id": 1, "slot_no": "A2", "sku_name": "可乐", "capacity": 18}
    exact = build_fill_lines([{**base, "stock": 18, "in_transit": 0}])[0]
    below = build_fill_lines([{**base, "stock": 17, "in_transit": 0}])[0]
    above = build_fill_lines([{**base, "stock": 18, "in_transit": 1}])[0]
    assert (exact.status, exact.fill_qty) == ("full", 0)
    assert (below.status, below.fill_qty) == ("need_fill", 1)
    assert (above.status, above.fill_qty) == ("overbooked", 0)

def test_statuses_are_disjoint_and_counts_partition_lines():
    lanes = [
        {"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0},
        {"id": 2, "slot_no": "A2", "sku_name": "可乐", "capacity": 18, "stock": 18, "in_transit": 0},
        {"id": 3, "slot_no": "C2", "sku_name": "口香糖", "capacity": 24, "stock": 24, "in_transit": 2},
    ]
    s = summarize(build_fill_lines(lanes))
    assert s["need_fill_count"] == 1
    assert s["full_count"] == 1
    assert s["overbooked_count"] == 1
    statuses = [l["status"] for l in s["lines"]]
    assert statuses.count("overbooked") == s["overbooked_count"]
    assert statuses.count("full") == s["full_count"]

def test_overbooked_reason_is_separate_from_full():
    lanes = [{"id": 1, "slot_no": "C2", "sku_name": "口香糖", "capacity": 24, "stock": 24, "in_transit": 2}]
    line = build_fill_lines(lanes)[0]
    assert "超占" in line.reason
    assert "满仓" not in line.reason
