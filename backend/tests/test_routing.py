from app.services.routing import Point, Stop, plan_route, walking_distance


def test_same_aisle_distance():
    assert walking_distance(Point(2, 1), Point(2, 4), rows=6) == 6.0


def test_cross_aisle_uses_shorter_cross_aisle():
    # both near the back -> going via back cross-aisle is shorter
    d = walking_distance(Point(1, 6), Point(3, 6), rows=6)
    assert d == 2 * 3.0 + 2 * 2.0


def test_route_is_never_worse_than_list_order():
    stops = [Stop("a", "Milk", 7, 5), Stop("b", "Bread", 1, 2), Stop("c", "Dal", 4, 3), Stop("d", "Chips", 2, 6),
             Stop("e", "Soap", 8, 1), Stop("f", "Eggs", 1, 5)]
    r = plan_route(stops, aisles=8, rows=6)
    assert len(r["steps"]) == 6
    assert r["total_distance_m"] <= r["unoptimised_distance_m"]
    aisles = [s["aisle"] for s in r["steps"]]
    assert aisles[0] == 1  # starts near the entrance (aisle 1)


def test_items_on_same_shelf_are_grouped():
    r = plan_route([Stop("a", "A", 3, 2), Stop("b", "B", 3, 2)], aisles=8, rows=6)
    assert len(r["steps"]) == 1 and len(r["steps"][0]["items"]) == 2
