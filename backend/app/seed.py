"""Demo data: 3 stores, catalogue, every staff role, a family sharing a list, and 60 days
of order history so analytics have something to show.

    python -m app.seed            # create tables + seed (skips if already seeded)
    python -m app.seed --reset    # drop everything and reseed
"""
import random
import secrets
import sys
from datetime import date, datetime, timedelta

from app.core.database import Base, SessionLocal, engine, init_db
from app.core.security import hash_password
from app.models import (Attendance, Category, CredentialRequest, ExitGate, Inventory, ListItem, ListMember, Offer,
                        Order, OrderItem, Product, Shift, ShoppingList, Store, SupportTicket, Task, User)
from app.models._mixins import utcnow

random.seed(42)
PASSWORD = "Password@123"
_PW_HASH = None

CATEGORIES = [("Fruits & Vegetables", "🥦"), ("Dairy, Bread & Eggs", "🥛"), ("Atta, Rice & Dal", "🌾"),
              ("Snacks & Munchies", "🍿"), ("Cold Drinks & Juices", "🧃"), ("Breakfast & Instant Food", "🥣"),
              ("Bakery & Biscuits", "🍪"), ("Personal Care", "🧴"), ("Cleaning Essentials", "🧽"),
              ("Meat, Fish & Eggs", "🍗")]

# name, brand, category index, unit, price, tags
PRODUCTS = [
    ("Banana Robusta", "Fresho", 0, "6 pcs", 48, ["vegan", "gluten_free"]),
    ("Tomato Hybrid", "Fresho", 0, "500 g", 32, ["vegan", "gluten_free"]),
    ("Onion", "Fresho", 0, "1 kg", 45, ["vegan", "gluten_free"]),
    ("Potato", "Fresho", 0, "1 kg", 38, ["vegan", "gluten_free"]),
    ("Apple Shimla", "Fresho", 0, "4 pcs", 140, ["vegan", "gluten_free"]),
    ("Coriander Leaves", "Fresho", 0, "100 g", 15, ["vegan", "gluten_free"]),
    ("Spinach (Palak)", "Fresho", 0, "250 g", 25, ["vegan", "gluten_free", "organic"]),
    ("Full Cream Milk", "Amul", 1, "1 L", 68, ["vegetarian", "gluten_free"]),
    ("Toned Milk", "Mother Dairy", 1, "500 ml", 28, ["vegetarian", "gluten_free"]),
    ("Almond Milk Unsweetened", "So Good", 1, "1 L", 299, ["vegan", "dairy_free", "gluten_free"]),
    ("Brown Bread", "Harvest Gold", 1, "400 g", 50, ["vegan"]),
    ("Gluten Free Bread", "Healthy Loaf", 1, "300 g", 120, ["vegetarian", "gluten_free"]),
    ("Paneer Fresh", "Amul", 1, "200 g", 90, ["vegetarian", "gluten_free"]),
    ("Butter Salted", "Amul", 1, "100 g", 58, ["vegetarian", "gluten_free"]),
    ("Curd Dahi", "Nestle", 1, "400 g", 45, ["vegetarian", "gluten_free"]),
    ("Tofu Firm", "Urban Platter", 1, "200 g", 110, ["vegan", "dairy_free", "gluten_free"]),
    ("Whole Wheat Atta", "Aashirvaad", 2, "5 kg", 265, ["vegan"]),
    ("Basmati Rice", "India Gate", 2, "1 kg", 145, ["vegan", "gluten_free"]),
    ("Toor Dal", "Tata Sampann", 2, "1 kg", 175, ["vegan", "gluten_free"]),
    ("Moong Dal", "Tata Sampann", 2, "500 g", 89, ["vegan", "gluten_free"]),
    ("Sunflower Oil", "Fortune", 2, "1 L", 155, ["vegan", "gluten_free"]),
    ("Iodised Salt", "Tata", 2, "1 kg", 28, ["vegan", "gluten_free"]),
    ("Sugar", "Madhur", 2, "1 kg", 52, ["vegan", "gluten_free"]),
    ("Potato Chips Classic Salted", "Lay's", 3, "52 g", 20, ["vegan", "gluten_free"]),
    ("Aloo Bhujia", "Haldiram's", 3, "200 g", 55, ["vegetarian"]),
    ("Roasted Peanuts", "Haldiram's", 3, "150 g", 40, ["vegan", "gluten_free"]),
    ("Dark Chocolate 55%", "Amul", 3, "150 g", 125, ["vegetarian", "gluten_free"]),
    ("Kurkure Masala Munch", "Kurkure", 3, "90 g", 20, ["vegetarian"]),
    ("Cola", "Coca-Cola", 4, "750 ml", 40, ["vegan", "gluten_free"]),
    ("Orange Juice", "Real", 4, "1 L", 115, ["vegan", "gluten_free"]),
    ("Coconut Water", "Raw Pressery", 4, "200 ml", 45, ["vegan", "gluten_free"]),
    ("Sugar Free Cold Coffee", "Sleepy Owl", 4, "200 ml", 80, ["vegetarian", "sugar_free"]),
    ("Corn Flakes", "Kellogg's", 5, "475 g", 199, ["vegan"]),
    ("Masala Oats", "Saffola", 5, "500 g", 185, ["vegetarian"]),
    ("Instant Noodles Masala", "Maggi", 5, "4 x 70 g", 56, ["vegetarian"]),
    ("Peanut Butter Crunchy", "Pintola", 5, "350 g", 199, ["vegan", "gluten_free"]),
    ("Honey", "Dabur", 5, "500 g", 225, ["vegetarian", "gluten_free"]),
    ("Marie Biscuits", "Britannia", 6, "250 g", 35, ["vegetarian"]),
    ("Good Day Cashew Cookies", "Britannia", 6, "200 g", 40, ["vegetarian"]),
    ("Multigrain Rusk", "Bonn", 6, "300 g", 65, ["vegetarian"]),
    ("Toothpaste", "Colgate", 7, "150 g", 105, ["vegan"]),
    ("Shampoo Anti-dandruff", "Head & Shoulders", 7, "340 ml", 399, []),
    ("Bath Soap (4 pack)", "Dove", 7, "4 x 100 g", 230, []),
    ("Hand Wash Refill", "Dettol", 7, "750 ml", 99, []),
    ("Dishwash Liquid", "Vim", 8, "750 ml", 165, []),
    ("Detergent Powder", "Surf Excel", 8, "1 kg", 140, []),
    ("Floor Cleaner", "Lizol", 8, "975 ml", 210, []),
    ("Garbage Bags Medium", "Ezee", 8, "30 pcs", 99, []),
    ("Farm Eggs", "Eggoz", 9, "6 pcs", 72, ["gluten_free"]),
    ("Chicken Breast Boneless", "Licious", 9, "450 g", 289, ["gluten_free"]),
    ("Rohu Fish Curry Cut", "FreshToHome", 9, "500 g", 249, ["gluten_free"]),
]

STORES = [
    ("BLR01", "FreshFlow Indiranagar", "100 Feet Rd, Indiranagar", "Bengaluru", "560038", 12.9719, 77.6412),
    ("BLR02", "FreshFlow Koramangala", "80 Feet Rd, 4th Block, Koramangala", "Bengaluru", "560034", 12.9352, 77.6245),
    ("MUM01", "FreshFlow Bandra West", "Hill Road, Bandra West", "Mumbai", "400050", 19.0544, 72.8337),
]

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Ishaan", "Ananya", "Vihaan", "Saanvi", "Arjun", "Priya", "Rohan",
         "Kavya", "Aditya", "Neha", "Siddharth", "Pooja", "Rahul", "Sneha", "Karan", "Tanvi", "Nikhil", "Riya"]
LAST = ["Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Patel", "Khan", "Singh", "Rao", "Das", "Menon", "Joshi"]

# rush-hour shape: weight of an order happening at each hour of the day
HOUR_WEIGHTS = [0, 0, 0, 0, 0, 0, 0, 3, 6, 7, 5, 4, 5, 6, 4, 3, 4, 6, 10, 12, 11, 8, 4, 1]


def mkuser(db, name, email, role, store_id=None, wage=None, phone=None, joined=None, code=None):
    global _PW_HASH
    _PW_HASH = _PW_HASH or hash_password(PASSWORD)  # hash once; bcrypt is deliberately slow
    u = User(full_name=name, email=email, role=role, store_id=store_id, hourly_wage=wage,
             phone=phone or f"+9198{random.randint(10_000_000, 99_999_999)}", password_hash=_PW_HASH,
             joined_on=joined, employee_code=code, auth_provider="email")
    db.add(u)
    db.flush()
    return u


def seed(db):
    cats = [Category(name=n, icon=i) for n, i in CATEGORIES]
    db.add_all(cats)
    db.flush()

    products = []
    for idx, (name, brand, ci, unit, price, tags) in enumerate(PRODUCTS, start=1):
        p = Product(sku=f"SKU{idx:05d}", barcode=f"890{idx:010d}", name=name, brand=brand, category_id=cats[ci].id,
                    unit=unit, price=price, mrp=round(price * random.choice([1, 1.05, 1.1, 1.15])),
                    cost_price=round(price * random.uniform(0.68, 0.82), 2), tags=tags,
                    description=f"{brand} {name}, {unit}.")
        products.append(p)
    db.add_all(products)
    db.flush()

    admin = mkuser(db, "Platform Admin", "admin@freshflow.app", "admin", phone="+919800000001")

    stores, staff_by_store = [], {}
    for si, (code, name, addr, city, pin, lat, lng) in enumerate(STORES):
        store = Store(code=code, name=name, address=addr, city=city, pincode=pin, latitude=lat, longitude=lng,
                      phone=f"+91 80 4{si}00 1000", aisle_count=8, rows_per_aisle=6)
        db.add(store)
        db.flush()
        stores.append(store)
        db.add(ExitGate(store_id=store.id, name="Exit Gate 1", api_key=f"gate-{code.lower()}-{secrets.token_hex(8)}"))
        db.add(ExitGate(store_id=store.id, name="Exit Gate 2", api_key=f"gate2-{code.lower()}-{secrets.token_hex(8)}"))

        # Layout: each category occupies one aisle (two small categories share aisle 8)
        for p in products:
            ci = p.category_id - cats[0].id
            aisle = min(ci + 1, 8)
            db.add(Inventory(store_id=store.id, product_id=p.id, quantity=random.randint(25, 120), aisle=aisle,
                             row=random.randint(1, 6), low_stock_threshold=10, restock_to=80))

        tag = code.lower()
        owner = mkuser(db, f"{random.choice(FIRST)} {random.choice(LAST)}", f"owner.{tag}@freshflow.app", "owner",
                       store.id, None, joined=date(2024, 1, 10), code=f"{code}-OWNER")
        store.owner_id = owner.id
        sm = mkuser(db, f"{random.choice(FIRST)} {random.choice(LAST)}", f"manager.{tag}@freshflow.app",
                    "store_manager", store.id, 260, joined=date(2024, 2, 1), code=f"{code}-0001")
        fms = [mkuser(db, f"{random.choice(FIRST)} {random.choice(LAST)}", f"floor{i}.{tag}@freshflow.app",
                      "floor_manager", store.id, 160, joined=date(2024, 3, 1 + i), code=f"{code}-00{10 + i}")
               for i in (1, 2)]
        workers = [mkuser(db, f"{random.choice(FIRST)} {random.choice(LAST)}", f"worker{i}.{tag}@freshflow.app",
                          "worker", store.id, random.choice([95, 100, 110]),
                          joined=date(2024, 4, i), code=f"{code}-01{i:02d}") for i in range(1, 6)]
        staff_by_store[store.id] = {"owner": owner, "sm": sm, "fms": fms, "workers": workers}

    db.flush()
    # Customers: a family that shares a list + general shoppers
    asha = mkuser(db, "Asha Verma", "asha@example.com", "customer", phone="+919811111111")
    rohan = mkuser(db, "Rohan Verma", "rohan@example.com", "customer", phone="+919822222222")
    asha.dietary_preferences, asha.preferred_store_id = ["vegetarian"], stores[0].id
    asha.default_address = "Flat 302, Lake View Apts, HAL 2nd Stage, Indiranagar, Bengaluru 560038"
    rohan.preferred_store_id = stores[0].id
    shoppers = [asha, rohan] + [mkuser(db, f"{random.choice(FIRST)} {random.choice(LAST)}", f"shopper{i}@example.com",
                                       "customer") for i in range(1, 41)]

    fam = ShoppingList(name="Verma Family Weekly", owner_id=asha.id, invite_code="VERMA1")
    db.add(fam)
    db.flush()
    db.add(ListMember(list_id=fam.id, user_id=rohan.id))
    for pname, qty, by in [("Full Cream Milk", 2, asha), ("Brown Bread", 1, asha), ("Banana Robusta", 1, rohan),
                           ("Paneer Fresh", 1, asha), ("Toor Dal", 1, asha), ("Marie Biscuits", 2, rohan),
                           ("Dishwash Liquid", 1, asha), ("Coriander Leaves", 1, rohan)]:
        p = next(x for x in products if x.name == pname)
        db.add(ListItem(list_id=fam.id, product_id=p.id, name=p.name, quantity=qty, added_by_id=by.id))

    now = utcnow()
    offers = [
        Offer(code="WELCOME50", title="50% off your first order (up to ₹100)", discount_percent=50, max_discount=100,
              min_order=199, starts_at=now - timedelta(days=90)),
        Offer(code="FRESH20", title="20% off Fruits & Vegetables", discount_percent=20, max_discount=80,
              category_id=cats[0].id, starts_at=now - timedelta(days=90)),
        Offer(code="SCANGO10", title="10% off Scan & Go in-store", discount_percent=10, max_discount=150,
              min_order=300, starts_at=now - timedelta(days=90)),
        Offer(code="DAIRY15", store_id=stores[0].id, title="15% off Dairy at Indiranagar", discount_percent=15,
              max_discount=60, category_id=cats[1].id, starts_at=now - timedelta(days=60)),
    ]
    db.add_all(offers)
    db.flush()

    # 60 days of historical paid orders
    for store in stores:
        for day_offset in range(60, -1, -1):
            day = (now - timedelta(days=day_offset)).date()
            weekend = day.weekday() >= 5
            for _ in range(random.randint(55, 75) + (25 if weekend else 0)):
                hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
                ts = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=random.randint(0, 59))
                if ts > now:
                    continue
                basket = random.sample(products, random.randint(2, 7))
                lines = [(p, random.choice([1, 1, 1, 2, 3])) for p in basket]
                subtotal = sum(p.price * q for p, q in lines)
                offer = random.choice([None] * 6 + offers[:3] + ([offers[3]] if store.id == stores[0].id else []))
                discount = 0.0
                if offer and subtotal >= offer.min_order:
                    discount = min(subtotal * offer.discount_percent / 100, offer.max_discount)
                else:
                    offer = None
                mode = random.choices(["delivery", "pickup", "instore"], weights=[55, 15, 30])[0]
                fee = 25.0 if mode == "delivery" and subtotal - discount < 199 else 0.0
                tax = round((subtotal - discount) * 0.05, 2)
                o = Order(number=f"FF{ts:%y%m%d}{secrets.token_hex(3).upper()}", user_id=random.choice(shoppers).id,
                          store_id=store.id, fulfilment=mode, status="completed", subtotal=subtotal,
                          discount=round(discount, 2), delivery_fee=fee, tax=tax,
                          total=round(subtotal - discount + tax + fee, 2),
                          cost_total=round(sum(p.cost_price * q for p, q in lines), 2),
                          offer_id=offer.id if offer else None, payment_provider="mock",
                          payment_method=random.choice(["upi", "upi", "card", "google_pay", "apple_pay", "paypal"]),
                          paid_at=ts, created_at=ts, receipt_nonce=secrets.token_hex(8),
                          exit_verified_at=ts + timedelta(minutes=2) if mode == "instore" else None)
                for p, q in lines:
                    o.items.append(OrderItem(product_id=p.id, name=p.name, quantity=q, unit_price=p.price,
                                             unit_cost=p.cost_price))
                db.add(o)

    # Staff: attendance for the last 30 days, shifts for the next 7, some tasks
    for store in stores:
        s = staff_by_store[store.id]
        team = [s["sm"], *s["fms"], *s["workers"]]
        for d in range(30, 0, -1):
            day = (now - timedelta(days=d)).date()
            for u in team:
                if random.random() < 0.12:
                    continue  # absent
                morning = u.id % 2 == 0
                start = datetime.combine(day, datetime.min.time()) + timedelta(
                    hours=7 if morning else 14, minutes=random.randint(-10, 25))
                db.add(Attendance(store_id=store.id, user_id=u.id, clock_in=start,
                                  clock_out=start + timedelta(hours=8, minutes=random.randint(-20, 40))))
        for d in range(0, 7):
            day = (now + timedelta(days=d)).date()
            for u in team:
                morning = (u.id + d) % 2 == 0
                st = datetime.combine(day, datetime.min.time()) + timedelta(hours=7 if morning else 14)
                db.add(Shift(store_id=store.id, user_id=u.id, starts_at=st, ends_at=st + timedelta(hours=8),
                             label="Morning" if morning else "Evening", created_by_id=s["sm"].id))
        w = s["workers"]
        db.add_all([
            Task(store_id=store.id, title="Face-up Aisle 3 (Atta & Dal)", description="Pull stock forward, fix labels",
                 assigned_to_id=w[0].id, assigned_by_id=s["fms"][0].id, priority="normal"),
            Task(store_id=store.id, title="Check expiry dates in dairy chiller", priority="high",
                 assigned_to_id=w[1].id, assigned_by_id=s["sm"].id, status="in_progress"),
            Task(store_id=store.id, title="Clean spill near Aisle 5", priority="urgent", assigned_to_id=w[2].id,
                 assigned_by_id=s["fms"][1].id, status="done", completion_note="Cleaned and placed wet-floor sign.",
                 completed_at=now - timedelta(hours=2)),
            Task(store_id=store.id, title="Prepare weekly stock count sheet", assigned_to_id=s["fms"][0].id,
                 assigned_by_id=s["sm"].id, status="reviewed", completion_note="Uploaded to drive.",
                 completed_at=now - timedelta(days=2), manager_rating=5, manager_feedback="Excellent, very thorough."),
        ])
        db.add(CredentialRequest(store_id=store.id, requested_by_id=s["sm"].id, full_name="Farhan Qureshi",
                                 email=f"farhan.{store.code.lower()}@example.com", phone="+919833333333",
                                 role="worker", hourly_wage=100, joining_date=(now + timedelta(days=5)).date(),
                                 notes="Night-shift stocker", status="pending_owner"))
        db.add(CredentialRequest(store_id=store.id, requested_by_id=s["sm"].id, full_name="Lakshmi Pillai",
                                 email=f"lakshmi.{store.code.lower()}@example.com", phone="+919844444444",
                                 role="floor_manager", hourly_wage=165, joining_date=(now + timedelta(days=3)).date(),
                                 status="pending_admin", owner_note="Approved — strong references."))
        db.add(SupportTicket(store_id=store.id, raised_by_id=s["sm"].id, category="gate", priority="high",
                             subject="Exit Gate 2 scanner intermittently not reading QR",
                             description="Happens mostly in the evening rush. Rebooting fixes it for ~1 hour."))

    # a couple of low-stock items to show alerts
    for inv in db.query(Inventory).filter(Inventory.store_id == stores[0].id).limit(3):
        inv.quantity = random.randint(3, 9)
    db.commit()


def main():
    reset = "--reset" in sys.argv
    if reset:
        Base.metadata.drop_all(bind=engine)
    init_db()
    with SessionLocal() as db:
        if db.query(User).first():
            print("Database already seeded (use --reset to start over).")
            return
        seed(db)
        # raise restock alerts for the low items
        from app.services.inventory import raise_restock_alert

        for inv in db.query(Inventory).filter(Inventory.quantity <= Inventory.low_stock_threshold):
            raise_restock_alert(db, inv)
        db.commit()
    print(f"Seeded. All demo accounts use password: {PASSWORD}")
    print("  admin@freshflow.app | owner.blr01@freshflow.app | manager.blr01@freshflow.app")
    print("  floor1.blr01@freshflow.app | worker1.blr01@freshflow.app | asha@example.com | rohan@example.com")


if __name__ == "__main__":
    main()
