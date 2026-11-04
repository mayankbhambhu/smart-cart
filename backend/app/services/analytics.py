"""Business analytics for a store over any date range.

Aggregation is done in Python over the period's paid orders so the same code runs on
SQLite and PostgreSQL. For multi-year, multi-store volumes move these to SQL views or a
warehouse (the function signatures stay the same)."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from app.models import Attendance, Category, Inventory, Offer, Order, OrderItem, Product, User
from app.models._mixins import utcnow

PAID = ("paid", "preparing", "ready", "out_for_delivery", "completed")


def resolve_range(period: str, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    today = utcnow().date()
    if period == "custom" and start and end:
        s, e = start, end
    elif period == "week":
        s, e = today - timedelta(days=6), today
    elif period == "month":
        s, e = today.replace(day=1), today
    elif period == "year":
        s, e = today.replace(month=1, day=1), today
    else:  # today
        s, e = today, today
    return datetime.combine(s, datetime.min.time()), datetime.combine(e, datetime.max.time())


def store_report(db: Session, store_id: int | None, start: datetime, end: datetime) -> dict:
    q = db.query(Order).options(selectinload(Order.items)).filter(
        Order.status.in_(PAID), Order.paid_at >= start, Order.paid_at <= end)
    if store_id:
        q = q.filter(Order.store_id == store_id)
    orders = q.all()

    gross = sum(o.subtotal for o in orders)
    discounts = sum(o.discount for o in orders)
    net_sales = gross - discounts  # revenue excluding tax and delivery fee
    cogs = sum(o.cost_total for o in orders)
    profit = net_sales - cogs
    tax = sum(o.tax for o in orders)

    product_units: Counter = Counter()
    product_revenue: Counter = Counter()
    product_profit: Counter = Counter()
    by_hour = [0] * 24
    heat = [[0] * 24 for _ in range(7)]  # weekday x hour
    daily: dict[str, dict] = defaultdict(lambda: {"sales": 0.0, "profit": 0.0, "orders": 0})
    fulfilment: Counter = Counter()
    offer_uses: Counter = Counter()
    offer_discount: Counter = Counter()
    offer_revenue: Counter = Counter()
    customers = set()

    bucket_monthly = (end - start).days > 92
    for o in orders:
        customers.add(o.user_id)
        fulfilment[o.fulfilment] += 1
        by_hour[o.paid_at.hour] += 1
        heat[o.paid_at.weekday()][o.paid_at.hour] += 1
        key = o.paid_at.strftime("%Y-%m") if bucket_monthly else o.paid_at.strftime("%Y-%m-%d")
        daily[key]["sales"] += o.subtotal - o.discount
        daily[key]["profit"] += o.subtotal - o.discount - o.cost_total
        daily[key]["orders"] += 1
        if o.offer_id:
            offer_uses[o.offer_id] += 1
            offer_discount[o.offer_id] += o.discount
            offer_revenue[o.offer_id] += o.subtotal - o.discount
        for it in o.items:
            product_units[it.product_id] += it.quantity
            product_revenue[it.product_id] += it.quantity * it.unit_price
            product_profit[it.product_id] += it.quantity * (it.unit_price - it.unit_cost)

    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(list(product_units) or [0]))}
    cats = {c.id: c.name for c in db.query(Category)}
    category_sales: Counter = Counter()
    for pid, rev in product_revenue.items():
        category_sales[cats.get(products[pid].category_id, "Other")] += rev

    def prod_row(pid: int) -> dict:
        p = products[pid]
        return {"product_id": pid, "name": p.name, "units": product_units[pid],
                "revenue": round(product_revenue[pid], 2), "profit": round(product_profit[pid], 2)}

    offers = {o.id: o for o in db.query(Offer).filter(Offer.id.in_(list(offer_uses) or [0]))}
    peak_hours = sorted(range(24), key=lambda h: by_hour[h], reverse=True)[:3]
    days = max((end.date() - start.date()).days + 1, 1)

    inv_q = db.query(Inventory)
    if store_id:
        inv_q = inv_q.filter(Inventory.store_id == store_id)
    low_stock = [{"product": i.product.name, "quantity": i.quantity, "aisle": i.aisle, "row": i.row}
                 for i in inv_q.filter(Inventory.quantity <= Inventory.low_stock_threshold).limit(20)]
    # Dead stock: stocked items with zero sales in the period
    dead = [i.product.name for i in inv_q.limit(500) if i.product_id not in product_units][:10]

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "kpis": {
            "orders": len(orders), "customers": len(customers),
            "gross_sales": round(gross, 2), "discounts": round(discounts, 2), "net_sales": round(net_sales, 2),
            "cost_of_goods": round(cogs, 2), "gross_profit": round(profit, 2),
            "margin_percent": round(profit / net_sales * 100, 1) if net_sales else 0,
            "tax_collected": round(tax, 2),
            "avg_basket": round(net_sales / len(orders), 2) if orders else 0,
            "items_sold": sum(product_units.values()),
            "avg_daily_sales": round(net_sales / days, 2),
        },
        "top_products": [prod_row(pid) for pid, _ in product_units.most_common(10)],
        "top_profit_products": [prod_row(pid) for pid, _ in product_profit.most_common(5)],
        "category_sales": [{"category": k, "revenue": round(v, 2)} for k, v in category_sales.most_common()],
        "offers": [{"code": offers[oid].code, "title": offers[oid].title, "uses": n,
                    "discount_given": round(offer_discount[oid], 2), "revenue": round(offer_revenue[oid], 2)}
                   for oid, n in offer_uses.most_common()],
        "orders_by_hour": by_hour,
        "rush_hours": [{"hour": h, "label": f"{h:02d}:00–{(h + 1) % 24:02d}:00", "orders": by_hour[h]}
                       for h in peak_hours if by_hour[h]],
        "heatmap": heat,
        "series": [{"period": k, **{m: round(v, 2) for m, v in daily[k].items()}} for k in sorted(daily)],
        "fulfilment_mix": dict(fulfilment),
        "low_stock": low_stock,
        "dead_stock": dead,
    }


def staff_hours(db: Session, store_id: int, start: datetime, end: datetime) -> list[dict]:
    staff = db.query(User).filter(User.store_id == store_id).all()
    rows = db.query(Attendance).filter(Attendance.store_id == store_id, Attendance.clock_in >= start,
                                       Attendance.clock_in <= end).all()
    per: dict[int, dict] = {u.id: {"user_id": u.id, "name": u.full_name, "role": u.role, "hours": 0.0,
                                   "days_present": set(), "wage": u.hourly_wage or 0} for u in staff}
    for a in rows:
        if a.user_id in per:
            per[a.user_id]["hours"] += a.hours
            per[a.user_id]["days_present"].add(a.clock_in.date())
    out = []
    for r in per.values():
        r["days_present"] = len(r["days_present"])
        r["hours"] = round(r["hours"], 2)
        r["earned"] = round(r["hours"] * r["wage"], 2)
        out.append(r)
    return sorted(out, key=lambda r: -r["hours"])
