# FreshFlow — quick-commerce + Scan & Go in-store shopping

A full-stack grocery platform in the style of 10-minute delivery apps, extended with
**store pickup** and **checkout-free in-store shopping**:

> Your family's shared list syncs live → the app routes you through the aisles
> (*"Aisle 4, Row 2"*) → items go into your phone's smart cart (shelf stock drops instantly) →
> tap **Checkout**, pay with Apple Pay / Google Pay / UPI → scan your receipt QR at the exit
> gate and walk out. No lines, no cashier.

Built mainly in **Python** (FastAPI API + three server-rendered FastAPI/Jinja2 dashboards).
The iOS/Android app is **React Native (Expo)**, since native payment sheets, camera barcode
scanning and Apple/Google sign-in need a native mobile toolkit.

| App | Who uses it | Local URL | Code |
|---|---|---|---|
| **API** (REST + WebSocket) | everything talks to it | http://localhost:8000/docs | `backend/` |
| **Customer dashboard** | shoppers (web) | http://localhost:8001 | `web/customer/` |
| **Store Operations dashboard** | owner · store manager · floor manager · worker | http://localhost:8002 | `web/store/` |
| **Admin Operations dashboard** | you + your team | http://localhost:8003 | `web/admin/` |
| **Mobile app** (iOS + Android) | shoppers | Expo | `mobile/` |

Each dashboard is a separate app with its own URL (its own "live link") and they all share one API and database.

---

## Architecture

```
 iOS / Android app (Expo)    Customer web    Store Ops web    Admin web      Exit-gate hardware
          │                       │               │               │               │ X-Gate-Key
          └──────── HTTPS (JWT) ──┴───────────────┴───────────────┴───────────────┘
                                          │
                          ┌───────────────▼────────────────┐
                          │  FastAPI  (backend/app)        │   WebSocket /ws  ← live: family lists,
                          │  routes → services → models    │   inventory, restock alerts, tasks,
                          └───────┬───────────────┬────────┘   gate events, notifications
                                  │               │
                         PostgreSQL / SQLite   Stripe · Razorpay (UPI) · PayPal · Twilio · Google · Apple
```

* **Auth**: JWT bearer tokens. Email+password (bcrypt), phone OTP (Twilio), Google ID token, Sign in with Apple.
* **Roles**: `customer`, `worker`, `floor_manager`, `store_manager`, `owner`, `admin`. Staff are scoped to their own store on every endpoint.
* **Real time**: an in-process WebSocket hub with channels `list:<id>`, `store:<id>`, `user:<id>`, `admin`.
* **Payments**: card, Apple Pay and Google Pay go through a Stripe PaymentIntent (the native PaymentSheet on the phone, the Payment Element on the web). UPI uses a Razorpay Payment Link. PayPal uses Orders v2. The server always re-verifies with the gateway before issuing a receipt. `PAYMENTS_MODE=mock` runs the whole flow without gateway accounts.
* **Exit gate**: the receipt code is `FF1.<order>.<nonce>.<HMAC>`. Forged codes are rejected before any database lookup. A code is single-use, bound to one store, and expires after a configurable time.

## Features → where they live

### 1. Customer (web `web/customer` + mobile `mobile/`)
| Feature | Implementation |
|---|---|
| Delivery / **store pickup** (slot booking with capacity) / **in-store** mode | `api/routes/cart.py`, `stores.py → /pickup-slots` |
| Item **location** ("Aisle 4, Row 2") + running total | `Inventory.aisle/row`, shown on every product, list and cart line |
| **Collaborative family lists**, live sync | `api/routes/lists.py` + WebSocket `list:<id>`; join by invite code |
| **Efficient aisle routing** | `services/routing.py`: exact walking-distance matrix (aisles joined by front and back cross-aisles), then nearest-neighbour + 2-opt; drawn as an SVG store map |
| **Smart cart**: in-store adds deduct shelf stock instantly | `cart.py::_set_line` → `services/inventory.adjust_stock` |
| Barcode scanning | mobile `app/scan.tsx` (camera); web: type or scan into the field |
| **One-tap checkout**: Stripe (card / Apple Pay / Google Pay), UPI, PayPal | `services/payments.py`, mobile `lib/payments.ts` |
| **Digital receipt QR** → **exit gate verifies and opens** | `orders.py → receipt.png`, mobile `components/QRCode.tsx` (renders offline), `gate.py` |
| Login: email, Google, Apple, phone OTP | `api/routes/auth.py`, `services/auth_providers.py`, mobile `app/login.tsx` |
| Profile: payment methods (tokenised), dietary preferences (filters the catalogue), purchase history | `/me`, `/me/payment-methods`, `/orders` |
| **Store locator + stock check before leaving home** | `/stores?lat&lng` (sorted by distance), `/stock-check?q=` |

### 2. Store Operations (`web/store`), role-aware menu
| Feature | Who |
|---|---|
| **Real-time inventory**: live quantity updates. Below threshold, a restock alert fires and a task is **auto-assigned** to the least-busy worker, who gets an alert | all staff (workers can only record restocks) |
| **Business analysis**: net sales, gross profit and margin, profit after staff cost, best sellers, most-liked offers, **rush hours** + weekday×hour heatmap, category mix, fulfilment mix, low and dead stock, for **today / week / month / year / any custom range** | owner, store manager |
| **Work assigning**: assign → employee alerted live → they start → mark done **with a report** → manager **reviews and rates** (★1–5) | managers assign; floor managers assign to workers |
| **Shifts**: weekly grid, overlap protection, repeat for N days | managers |
| **Attendance**: clock in/out, who came, at what time, when they left, hours, days present, wages earned | supervisors |
| **Employee onboarding**: Store Manager raises → **Owner** approves / sends back / rejects → **Admin** issues credentials / sends back / rejects. A request sent back can be edited and resubmitted | store manager, owner |
| Order fulfilment (pickup/delivery status), exit-gate monitor + simulator (with camera), offers, support tickets | as appropriate |

### 3. Admin Operations (`web/admin`)
* Review credential requests and **issue logins** (temporary password, shown once; the employee is forced to change it at first login).
* **Remove employees** who left or were fired: login revoked immediately, open tasks flagged for reassignment, attendance kept for payroll. Reset passwords.
* All **stores** with owner details, employee lists (name, phone, joining date, wage), monthly KPIs, and onboarding of new stores (which creates the owner login and an exit gate).
* **Store issues** (support tickets) with responses that notify the store.
* Platform overview: sales across stores, pending work.

---

## File structure

```
freshflow/
├── README.md
├── .env.example                 # every setting, documented
├── docker-compose.yml           # Postgres + API + 3 dashboards
├── render.yaml                  # one-click cloud deploy: 4 services = 4 live links
├── scripts/
│   ├── dev.sh                   # run everything locally (seeds demo data)
│   └── smoke_test.py            # end-to-end: every page, every role, Scan & Go → gate
│
├── backend/                     # ── FastAPI API (Python) ───────────────────────────
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # app factory, routers, CORS, lifespan
│   │   ├── seed.py              # demo data: 3 stores, catalogue, staff, 60 days of sales
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings (env vars)
│   │   │   ├── database.py      # SQLAlchemy engine/session (SQLite or PostgreSQL)
│   │   │   ├── security.py      # bcrypt, JWT, OTP hashing, signed receipt codes
│   │   │   ├── deps.py          # current user, role guards, store scoping
│   │   │   └── realtime.py      # WebSocket pub/sub hub
│   │   ├── models/              # SQLAlchemy 2.0 ORM
│   │   │   ├── user.py          # User(+roles), OTPCode, PaymentMethod, Notification
│   │   │   ├── store.py         # Store(+aisle layout), ExitGate, GateEvent
│   │   │   ├── catalog.py       # Category, Product, Inventory(aisle,row), Offer, RestockAlert
│   │   │   ├── shopping.py      # ShoppingList, ListMember, ListItem, Cart, CartItem
│   │   │   ├── order.py         # Order, OrderItem
│   │   │   ├── staff.py         # CredentialRequest, Task, Shift, Attendance
│   │   │   └── support.py       # SupportTicket
│   │   ├── schemas/__init__.py  # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── routing.py       # aisle route optimiser (distance matrix + 2-opt)
│   │   │   ├── inventory.py     # stock moves, thresholds, auto restock tasks
│   │   │   ├── pricing.py       # subtotal, offers, delivery fee, GST
│   │   │   ├── payments.py      # Stripe / Razorpay UPI / PayPal / mock adapters
│   │   │   ├── orders.py        # cart → order → paid lifecycle
│   │   │   ├── analytics.py     # sales, profit, rush hours, offers, staff hours
│   │   │   ├── auth_providers.py# Google & Apple token verification, SMS
│   │   │   └── notify.py        # persisted + live notifications
│   │   └── api/routes/
│   │       ├── auth.py          # /auth/*, /me/*
│   │       ├── stores.py        # store locator, catalogue, stock check, pickup slots
│   │       ├── lists.py         # family lists + route
│   │       ├── cart.py          # cart / smart cart
│   │       ├── orders.py        # checkout, payment confirm, webhooks, receipts
│   │       ├── gate.py          # exit-gate verification
│   │       ├── store_ops.py     # inventory, alerts, store orders, offers, gates
│   │       ├── people.py        # credential requests, tasks, shifts, attendance
│   │       ├── analytics.py     # business analysis
│   │       ├── support.py       # tickets (store side)
│   │       ├── admin.py         # admin: approvals, stores, employees, tickets
│   │       └── ws.py            # WebSocket endpoint with per-channel authorisation
│   └── tests/                   # pytest: 19 tests, run on SQLite and PostgreSQL
│
├── web/                         # ── Three dashboards (Python: FastAPI + Jinja2 + htmx) ─
│   ├── Dockerfile               # one image, APP=customer|store|admin
│   ├── requirements.txt
│   ├── shared/                  # API client, session auth, formatting (₹ Indian grouping)
│   │   ├── __init__.py
│   │   ├── templates/           # base layout, login, flash messages
│   │   └── static/              # app.css design system, live.js, vendored Chart.js/htmx
│   ├── customer/  app.py + templates/   # shop, cart, pay, Scan & Go map, lists, orders, profile
│   ├── store/     app.py + templates/   # overview, tasks, inventory, orders, gate, shifts,
│   │                                    # attendance, team & onboarding, analysis, offers, support
│   └── admin/     app.py + templates/   # overview, requests, stores, employees, tickets
│
└── mobile/                      # ── iOS + Android (Expo SDK 54, Expo Router, TypeScript) ──
    ├── app.json                 # permissions, Apple Sign-In, Stripe/Google Pay plugins
    ├── eas.json                 # cloud builds for the App Store / Play Store
    └── src/
        ├── app/                 # screens (file-based routes)
        │   ├── _layout.tsx      # providers: Stripe, auth, cart
        │   ├── login.tsx        # email · phone OTP · Google · Apple
        │   ├── (tabs)/index.tsx     # shop (store + mode switch, diet filter)
        │   ├── (tabs)/instore.tsx   # Scan & Go: route map, picked ✓, smart cart
        │   ├── (tabs)/lists.tsx     # family lists
        │   ├── (tabs)/orders.tsx    # purchase history
        │   ├── (tabs)/profile.tsx   # details, diet, payment methods
        │   ├── cart.tsx         # checkout: slots, address, offers, Apple/Google Pay/UPI
        │   ├── scan.tsx         # camera barcode → smart cart
        │   ├── stores.tsx       # GPS store locator + stock check
        │   ├── list/[id].tsx    # live-synced list
        │   └── order/[id].tsx   # receipt QR for the exit gate
        ├── components/          # ui kit, ProductCard, StoreMap (SVG), QRCode (offline)
        └── lib/                 # api client, auth, cart, live (WebSocket), payments, theme
```

## Run it locally

```bash
./scripts/dev.sh
```

That creates a virtualenv, seeds demo data into SQLite and starts all four servers.
Every demo account uses the password **`Password@123`**:

| Dashboard | Logins |
|---|---|
| Customer (8001) | `asha@example.com`, `rohan@example.com` (they share the *Verma Family Weekly* list) |
| Store Ops (8002) | `owner.blr01@freshflow.app`, `manager.blr01@…`, `floor1.blr01@…`, `worker1.blr01@…` (also `blr02`, `mum01`) |
| Admin (8003) | `admin@freshflow.app` |

**Try the headline flow:** log in as Rohan → **Scan & Go** → pick a store. In a second
browser, log in as Asha and add "Curd" to the family list. Rohan's route re-plans live. Tap
**Picked ✓** on a few items, then **Checkout** and **Pay**. Copy the receipt code into
Store Ops → **Exit gates** to see the gate open. Re-scanning within 2 minutes is allowed
(the shopper tapped twice); reusing the receipt after that is rejected.

With PostgreSQL instead of SQLite: `docker compose up --build`, then `docker compose exec api python -m app.seed`.

### Mobile app

```bash
cd mobile && npm install
```

```bash
EXPO_PUBLIC_API_URL=http://<your-computer-LAN-IP>:8000 npx expo start
```

Shopping, lists, routing, receipts and mock payments work in **Expo Go**. Stripe's
PaymentSheet (Apple Pay / Google Pay) and Sign in with Apple need a **development build**:
run `npx eas-cli build --profile development`, or `npx expo run:ios` / `npx expo run:android`.
App Store / Play Store builds: `npx eas-cli build --profile production`.

### Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

```bash
cd backend && TEST_DATABASE_URL=postgresql://user:pass@localhost/freshflow_test ../.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python scripts/smoke_test.py
```

The smoke test needs all four servers running (`./scripts/dev.sh`).

```bash
cd mobile && npx tsc --noEmit
```

## Going live: what you need to plug in

| Item | Setting(s) | Without it |
|---|---|---|
| Stripe (cards, **Apple Pay**, **Google Pay**) | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `PAYMENTS_MODE=live`; Apple Pay merchant ID `merchant.app.freshflow` | sandbox mock payments |
| **UPI** (Razorpay Payment Links) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`; webhook → `/payments/razorpay/webhook` | sandbox mock |
| PayPal | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_URL` | sandbox mock |
| Google login | `GOOGLE_CLIENT_IDS` (API) + `extra.googleClientIds` (mobile) | button disabled |
| Apple login | `APPLE_BUNDLE_IDS`, Apple developer account | iOS button errors |
| Phone OTP SMS | `TWILIO_*` | code shown on screen in DEBUG |
| Production secrets | `SECRET_KEY`, `SESSION_SECRET`, `DEBUG=false`, `CORS_ORIGINS` | insecure defaults |

**Deploy:** push to GitHub, then on Render choose *New → Blueprint* and pick `render.yaml`.
That creates the database, the API and three dashboard services, each with its own URL.
Update `API_URL` / `PUBLIC_API_URL` if your API URL differs.

## Design notes and limits

* Inventory is decremented **when an item enters an in-store smart cart** (as specified) and
  restored if it is removed. Delivery and pickup orders decrement at payment. A production
  system would also expire abandoned in-store carts (a scheduled job calling `DELETE /cart`).
* The WebSocket hub is in-process. To run more than one API instance, add Redis pub/sub
  (the `REDIS_URL` setting is reserved for this).
* Analytics aggregate in Python so the same code runs on SQLite and PostgreSQL. At large
  scale, move them to SQL views or a warehouse; the function signatures stay the same.
* Tables are created with `create_all` on startup. Add Alembic migrations before the first production schema change.
