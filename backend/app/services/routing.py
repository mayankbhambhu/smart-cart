"""In-store route planning.

Store model: aisles 1..A run front-to-back and are laid out left-to-right; each aisle has
rows 1..R (shelf sections) from front to back. Shoppers can only switch aisles through the
front cross-aisle (row 0) or the back cross-aisle (row R+1). The entrance is at the front of
aisle 1 and the checkout/exit is at the front of the last aisle.

We build an exact walking-distance matrix under that constraint, then solve the
open travelling-salesman path (fixed start and end) with nearest-neighbour + 2-opt.
For grocery-sized lists (< 60 stops) this runs in milliseconds.
"""
from dataclasses import dataclass, field

AISLE_WIDTH = 3.0  # metres between neighbouring aisle centre-lines
ROW_LENGTH = 2.0  # metres per shelf section


@dataclass(frozen=True)
class Point:
    aisle: int
    row: int  # 0 = front cross-aisle, rows+1 = back cross-aisle


@dataclass
class Stop:
    key: str
    label: str
    aisle: int
    row: int
    payload: dict = field(default_factory=dict)


def walking_distance(a: Point, b: Point, rows: int) -> float:
    if a.aisle == b.aisle:
        return abs(a.row - b.row) * ROW_LENGTH
    across = abs(a.aisle - b.aisle) * AISLE_WIDTH
    via_front = (a.row + b.row) * ROW_LENGTH
    via_back = ((rows + 1 - a.row) + (rows + 1 - b.row)) * ROW_LENGTH
    return across + min(via_front, via_back)


def _path_len(order: list[int], dist: list[list[float]]) -> float:
    return sum(dist[order[i]][order[i + 1]] for i in range(len(order) - 1))


def solve_path(dist: list[list[float]]) -> list[int]:
    """Node 0 = start, node n-1 = end. Returns visiting order including both."""
    n = len(dist)
    if n <= 2:
        return list(range(n))
    end = n - 1
    unvisited = set(range(1, end))
    order = [0]
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: (dist[last][j], j))
        order.append(nxt)
        unvisited.remove(nxt)
    order.append(end)

    improved = True
    while improved:
        improved = False
        for i in range(1, len(order) - 2):
            for k in range(i + 1, len(order) - 1):
                a, b = order[i - 1], order[i]
                c, d = order[k], order[k + 1]
                delta = dist[a][c] + dist[b][d] - dist[a][b] - dist[c][d]
                if delta < -1e-9:
                    order[i : k + 1] = reversed(order[i : k + 1])
                    improved = True
    return order


def plan_route(stops: list[Stop], aisles: int, rows: int, start: Point | None = None) -> dict:
    start = start or Point(1, 0)
    end = Point(aisles, 0)
    # merge stops on the same shelf section so the shopper stops once
    grouped: dict[tuple[int, int], list[Stop]] = {}
    for s in stops:
        grouped.setdefault((s.aisle, s.row), []).append(s)
    locations = list(grouped)
    points = [start] + [Point(a, r) for a, r in locations] + [end]
    dist = [[walking_distance(p, q, rows) for q in points] for p in points]
    order = solve_path(dist)

    steps = []
    for rank, idx in enumerate(order[1:-1], start=1):
        aisle, row = locations[idx - 1]
        items = grouped[(aisle, row)]
        steps.append({
            "step": rank,
            "aisle": aisle,
            "row": row,
            "distance_from_previous_m": round(dist[order[rank - 1]][idx], 1),
            "instruction": f"Go to Aisle {aisle}, Row {row}: pick " + ", ".join(s.label for s in items),
            "items": [{"key": s.key, "label": s.label, **s.payload} for s in items],
        })
    naive = _path_len(list(range(len(points))), dist)
    total = _path_len(order, dist)
    return {
        "start": {"aisle": start.aisle, "row": start.row, "label": "Entrance"},
        "end": {"aisle": end.aisle, "row": end.row, "label": "Exit / Scan-out gate"},
        "steps": steps,
        "total_distance_m": round(total, 1),
        "unoptimised_distance_m": round(naive, 1),
        "estimated_minutes": round(total / 50 + 0.4 * len(stops), 1),  # ~3 km/h + 24s per item
        "layout": {"aisles": aisles, "rows": rows},
    }
