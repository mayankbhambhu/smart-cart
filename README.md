# FreshFlow — quick-commerce + Scan & Go in-store shopping

A full-stack grocery platform in the style of 10-minute delivery apps, extended with
**store pickup** and **checkout-free in-store shopping**:

> Your family's shared list syncs live → the app routes you through the aisles
> (*"Aisle 4, Row 2"*) → items go into your phone's smart cart (shelf stock drops instantly) →
> tap **Checkout**, pay with Apple Pay / Google Pay / UPI → scan your receipt QR at the exit
> gate and walk out. No lines, no cashier.

Built mainly in **Python** (FastAPI API + a server-rendered FastAPI/Jinja2 website).
The iOS/Android app is **React Native (Expo)**, since native payment sheets, camera barcode
scanning and Apple/Google sign-in need a native mobile toolkit.

| App | Who uses it | Local URL | Code |
|---|---|---|---|
| **API** (REST + WebSocket) | everything talks to it | http://localhost:8000/docs | `backend/api/` |
| **Website**: one address, one login page | everyone | http://localhost:8001 | `backend/web/` + `web/` |
| ↳ Shop | shoppers | `/` | `backend/web/customer/` + `web/customer/` |
| ↳ Store Operations | owner · store manager · floor manager · worker | `/store` | `backend/web/store/` + `web/store/` |
| ↳ Admin | you + your team | `/admin` | `backend/web/admin/` + `web/admin/` |
| **Mobile app** (iOS + Android) | everyone | Expo | `app/` |

The website has **one address and one login page**. After signing in, the role on the account decides which
section opens: shoppers get the shop, store staff get `/store`, admins get `/admin`. The website and the
phone app share one API and database.

---

## Architecture

```
 iOS / Android app (Expo)    Customer web    Store Ops web    Admin web      Exit-gate hardware
          │                       │               │               │               │ X-Gate-Key
          └──────── HTTPS (JWT) ──┴───────────────┴───────────────┴───────────────┘
                                          │
                          ┌───────────────▼────────────────┐
                          │  FastAPI  (backend/api)        │   WebSocket /ws  ← live: family lists,
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

### 1. Customer (web `web/customer` + phone app `app/`)
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

Three main folders: **`backend/`** (all the Python server code), **`web/`** (the website's pages,
styles and scripts) and **`app/`** (the iOS + Android app). The website and the app both talk to
the same API in `backend/api`. The app has no server of its own, so there is no `backend/app`.

```
smart-cart/
├── README.md
├── .env.example                 # every setting, documented
├── docker-compose.yml           # Postgres + API + website
├── render.yaml                  # one-click cloud deploy: 4 services = 4 live links
├── scripts/
│   ├── dev.sh                   # run everything locally (seeds demo data)
│   └── smoke_test.py            # end-to-end: every page, every role, Scan & Go → gate
│
├── backend/                     # ══ BACKEND (Python) ══════════════════════════════════
│   ├── api/                     # ── the REST + WebSocket API, used by the website AND the app
│   │   ├── .env                 # your secrets and settings (not in git; see .env.example)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── main.py          # app factory, routers, CORS, lifespan
│   │   │   ├── seed.py          # demo data: 3 stores, catalogue, staff, 60 days of sales
│   │   │   ├── core/
│   │   │   │   ├── config.py    # pydantic-settings (env vars)
│   │   │   │   ├── database.py  # SQLAlchemy engine/session (SQLite or PostgreSQL)
│   │   │   │   ├── security.py  # bcrypt, JWT, OTP hashing, signed receipt codes
│   │   │   │   ├── deps.py      # current user, role guards, store scoping
│   │   │   │   └── realtime.py  # WebSocket pub/sub hub
│   │   │   ├── models/          # SQLAlchemy 2.0 ORM
│   │   │   │   ├── user.py      # User(+roles), OTPCode, PaymentMethod, Notification
│   │   │   │   ├── store.py     # Store(+aisle layout), ExitGate, GateEvent
│   │   │   │   ├── catalog.py   # Category, Product, Inventory(aisle,row), Offer, RestockAlert
│   │   │   │   ├── shopping.py  # ShoppingList, ListMember, ListItem, Cart, CartItem
│   │   │   │   ├── order.py     # Order, OrderItem
│   │   │   │   ├── staff.py     # CredentialRequest, Task, Shift, Attendance
│   │   │   │   └── support.py   # SupportTicket
│   │   │   ├── schemas/__init__.py  # Pydantic request/response models
│   │   │   ├── services/
│   │   │   │   ├── routing.py   # aisle route optimiser (distance matrix + 2-opt)
│   │   │   │   ├── inventory.py # stock moves, thresholds, auto restock tasks
│   │   │   │   ├── pricing.py   # subtotal, offers, delivery fee, GST
│   │   │   │   ├── payments.py  # Stripe / Razorpay UPI / PayPal / mock adapters
│   │   │   │   ├── orders.py    # cart → order → paid lifecycle
│   │   │   │   ├── analytics.py # sales, profit, rush hours, offers, staff hours
│   │   │   │   ├── auth_providers.py# Google & Apple token verification, SMS
│   │   │   │   └── notify.py    # persisted + live notifications
│   │   │   └── api/routes/
│   │   │       ├── auth.py      # /auth/*, /me/*
│   │   │       ├── stores.py    # store locator, catalogue, stock check, pickup slots
│   │   │       ├── lists.py     # family lists + route
│   │   │       ├── cart.py      # cart / smart cart
│   │   │       ├── orders.py    # checkout, payment confirm, webhooks, receipts
│   │   │       ├── gate.py      # exit-gate verification
│   │   │       ├── store_ops.py # inventory, alerts, store orders, offers, gates
│   │   │       ├── people.py    # credential requests, tasks, shifts, attendance
│   │   │       ├── analytics.py # business analysis
│   │   │       ├── support.py   # tickets (store side)
│   │   │       ├── admin.py     # admin: approvals, stores, employees, tickets
│   │   │       └── ws.py        # WebSocket endpoint with per-channel authorisation
│   │   └── tests/               # pytest: 31 tests, run on SQLite and PostgreSQL
│   │
│   └── web/                     # ── the website's server side (FastAPI + Jinja2)
│       ├── main.py              # one website: mounts the shop at /, /store and /admin
│       ├── Dockerfile           # one image, APP=customer|store|admin (build from the repo root)
│       ├── requirements.txt
│       ├── shared/
│       │   ├── __init__.py      # API client, shared sign-in session, role → section, ₹ formatting
│       │   └── signin.py        # the one login page for everybody
│       ├── customer/app.py      # shop, cart, pay, Scan & Go, lists, orders, profile
│       ├── store/app.py         # overview, tasks, inventory, orders, gate, shifts, attendance,
│       │                        # team & onboarding, analysis, offers, support
│       └── admin/app.py         # overview, requests, stores, employees, tickets
│
├── web/                         # ══ WEBSITE FRONTEND (HTML + CSS + JS, no Python) ═══════════
│   ├── shared/
│   │   ├── templates/           # base layout, login page, email-link page, flash messages
│   │   └── static/              # app.css design system, live.js, vendored Chart.js/htmx
│   ├── customer/templates/      # customer pages
│   ├── store/templates/         # store operations pages
│   └── admin/templates/         # admin pages
│
└── app/                         # ══ PHONE APP: iOS + Android (Expo SDK 58, TypeScript) ════
    ├── app.json                 # permissions, Apple Sign-In, Stripe/Google Pay plugins
    ├── eas.json                 # cloud builds for the App Store / Play Store
    └── src/
        ├── app/                 # screens (file-based routes)
        │   ├── _layout.tsx      # providers: Stripe, auth, cart
        │   ├── login.tsx        # email · phone OTP · Google · Apple · email link · SSO
        │   ├── (tabs)/          # shopper app: shop, Scan & Go, lists, orders, profile
        │   ├── staff/           # store operations app
        │   ├── admin/           # admin app
        │   ├── cart.tsx         # checkout: slots, address, offers, Apple/Google Pay/UPI
        │   ├── scan.tsx         # camera barcode → smart cart
        │   ├── stores.tsx       # GPS store locator + stock check
        │   ├── list/[id].tsx    # live-synced list
        │   └── order/[id].tsx   # receipt QR for the exit gate
        ├── components/          # ui kit, ProductCard, StoreMap (SVG), QRCode (offline)
        └── lib/                 # api client, auth, roles, sign-in, cart, live (WebSocket), payments
```

## One login, the right app for each role

Everyone signs in on the same login screen. The **role stored on the account** decides which app opens:

| Account role | Phone app opens | Website |
|---|---|---|
| `customer` | Shopping app (shop, Scan & Go, family lists, orders) | Shop (`/`) |
| `worker`, `floor_manager`, `store_manager`, `owner` | **Store operations** (`app/src/app/staff`): overview and clock-in, tasks, live inventory and restocks, orders, exit-gate QR scanner; analytics and team for managers | Store Operations (`/store`) |
| `admin` | **Admin** (`app/src/app/admin`): overview, credential requests, stores, employees, store issues | Admin (`/admin`) |

The routing lives in `app/src/lib/roles.ts`. Each section's layout also checks the role, so an account can never open another role's app, and the API enforces the same permissions on every request. Staff signing in with a temporary password from the admin team are sent to "Set your password" first. The website works the same way: one address and **one login page** (Email · Phone OTP · Sign up, plus Google, email link and SSO; the code is in `backend/web/shared/signin.py`, the page in `web/shared/templates/_login.html`). After signing in you go straight to your section, and opening another section's page sends you back to your own. `backend/web/main.py` puts the three sections together; they share one sign-in cookie, so logging out once logs you out everywhere.

## Sign-in options

The login screen (phone app and website) offers: **email + password**, **phone OTP**,
**Sign in with Google**, **Email me a sign-in link** (Firebase magic link), **single sign-on (SSO)**
and, on iPhone, **Sign in with Apple**. Each button switches on as soon as its settings are filled in
(`GET /auth/providers` tells the apps what is enabled); until then it shows "not set up". Whatever
the method, the **role on the account** still decides which app opens.

| Method | Who can use it | Backend settings |
|---|---|---|
| Google button | anyone; links to an existing account only if Google says the email is verified | `GOOGLE_WEB_CLIENT_ID` (+ `GOOGLE_IOS_CLIENT_ID`, `GOOGLE_ANDROID_CLIENT_ID` for the phone app) |
| Email magic link (Firebase) | anyone; a new email becomes a shopper account | `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `EMAIL_LINK_CONTINUE_URL` |
| Phone OTP (SMS) | anyone; a new number becomes a shopper account | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, **or free:** `SMSGATE_USERNAME`, `SMSGATE_PASSWORD` (without any, development mode shows the code on screen) |
| SSO (OpenID Connect) | **existing accounts only** (staff are still created through the approval chain) | `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_LABEL`, `API_PUBLIC_URL`, `SSO_ALLOWED_REDIRECTS` |

Removed (deactivated) employees are refused by every method.

**Google:** in Google Cloud Console → *APIs & Services → Credentials*, create an OAuth client of type
*Web application*. Add the website's address (e.g. `http://localhost:8001`) under *Authorized
JavaScript origins*. For the phone app also create iOS and Android clients. Put the web one in
`GOOGLE_WEB_CLIENT_ID`, and give the app its IDs through `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`,
`EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` and `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`. Google sign-in on the
phone needs a development build (`npx expo run:android` / `run:ios`); it does not run inside Expo Go.

**Email magic link:** in the Firebase console create a project, add a *Web app* (copy its `apiKey`,
`authDomain`, `projectId`), then *Authentication → Sign-in method → Email/Password* → enable
**Email link (passwordless sign-in)**. Under *Authentication → Settings → Authorized domains* add the
domain of the page in `EMAIL_LINK_CONTINUE_URL` (`localhost` is allowed by default). The link opens
that page: on a computer it finishes sign-in there; when the request came from the phone app it
forwards the link into the app. **To use it from a phone, that page must be reachable from the
phone on an authorized domain.** Use the deployed customer site, or a tunnel to it; a LAN IP
address can't be authorized.

**Phone OTP by SMS:** create a free Twilio account. In *Verify → Services* create a service with SMS
switched on, then copy the Account SID, Auth Token and the service's SID (`VA…`) into the settings.
Twilio Verify makes, sends and checks the code. As far as we know it also takes care of India's DLT
SMS rules, which plain SMS would need you to register for. People can type numbers any way
(`98111 11111`, `+91 98111-11111`); they're normalised to `+919811111111`, with
`PHONE_DEFAULT_COUNTRY_CODE` for 10-digit numbers. A Twilio *trial* account can only text numbers
you've verified in the Twilio console.

**Free alternative: SMS Gateway for Android.** Install the open-source *SMS Gateway for Android*
app (sms-gate.app, Android 5+) on a spare Android phone with a SIM and an SMS pack. Turn on *Cloud
server*, tap *Start*, and copy the username and password it shows into `SMSGATE_USERNAME` and
`SMSGATE_PASSWORD`. The backend generates the code and the phone texts it from its own SIM. With
the app's *Local server* instead, also set `SMSGATE_URL=http://<phone-ip>:8080/message` (the phone
and the backend must be on the same Wi-Fi). Twilio Verify wins if both are configured.

**SSO:** register an app with your identity provider (Microsoft Entra ID, Google Workspace, Okta,
Auth0, Keycloak...). Set its redirect URI to `{API_PUBLIC_URL}/auth/sso/callback` and copy the
issuer URL, client ID and secret into the settings. `OIDC_LABEL` is the button text (e.g. "Sign in
with Microsoft"). The flow uses the authorization code with PKCE, a one-time state and a nonce, and
checks the ID token signature, issuer and audience. Only a 2-minute single-use code is passed back
to the website or app, never the session token. Return addresses must start with an entry in
`SSO_ALLOWED_REDIRECTS`; remove `exp://` (Expo Go) in production.

## Run it locally

```bash
./scripts/dev.sh
```

That creates a virtualenv, seeds demo data into SQLite and starts the API and the website.
Open **http://localhost:8001** and sign in with any account below. The website opens the right section for it.
Every demo account uses the password **`Password@123`**:

| Opens | Logins |
|---|---|
| Shop (`/`) | `asha@example.com`, `rohan@example.com` (they share the *Verma Family Weekly* list) |
| Store Operations (`/store`) | `owner.blr01@freshflow.app`, `manager.blr01@…`, `floor1.blr01@…`, `worker1.blr01@…` (also `blr02`, `mum01`) |
| Admin (`/admin`) | `admin@freshflow.app` |

**Try the headline flow:** log in as Rohan → **Scan & Go** → pick a store. In a second
browser, log in as Asha and add "Curd" to the family list. Rohan's route re-plans live. Tap
**Picked ✓** on a few items, then **Checkout** and **Pay**. Copy the receipt code into
Store Ops → **Exit gates** to see the gate open. Re-scanning within 2 minutes is allowed
(the shopper tapped twice); reusing the receipt after that is rejected.

With PostgreSQL instead of SQLite: `docker compose up --build`, then `docker compose exec api python -m app.seed`.

### Mobile app (on your phone)

You need [Node.js](https://nodejs.org) (LTS) on your computer and the free **Expo Go** app on
your phone (App Store / Play Store). The phone and computer must be on the **same Wi-Fi**.

1. Start the backend with `./scripts/dev.sh`.
2. In a **second terminal**:

   ```bash
   cd app
   ```

   ```bash
   npm install
   ```

   ```bash
   npx expo start
   ```

   The app finds the API on your computer by itself (it uses the same address the phone
   loaded the app from). The login screen shows the server address it is using.
3. Scan the QR code that appears: with the **Camera app** on iPhone, or from inside **Expo Go**
   on Android. The app opens; log in with `asha@example.com` / `Password@123`.

Simulators work too: press `i` (iOS Simulator, needs Xcode) or `a` (Android emulator) in the
Expo terminal.

Troubleshooting: if the app can't log in ("Network request failed"), check that both devices
are on the same Wi-Fi, that the IP is right, and that macOS allowed incoming connections for
Python (System Settings → Network → Firewall). Open `http://<IP>:8000/health` in the phone's
browser to test.

Shopping, lists, routing, barcode scanning, receipts and sandbox payments work in Expo Go.
Real Apple Pay / Google Pay and Sign in with Apple need a **development build**
(`npx eas-cli build --profile development`, or `npx expo run:ios` / `npx expo run:android`).
App Store / Play Store builds: `npx eas-cli build --profile production`.

### Tests

```bash
cd backend/api && ../../.venv/bin/python -m pytest -q
```

```bash
cd backend/api && TEST_DATABASE_URL=postgresql://user:pass@localhost/freshflow_test ../../.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python scripts/smoke_test.py
```

The smoke test needs the API and the website running (`./scripts/dev.sh`). It also checks that every role lands in the right section and can't open the others.

```bash
cd app && npx tsc --noEmit
```

## Going live: what you need to plug in

| Item | Setting(s) | Without it |
|---|---|---|
| Stripe (cards, **Apple Pay**, **Google Pay**) | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `PAYMENTS_MODE=live`; Apple Pay merchant ID `merchant.app.freshflow` | sandbox mock payments |
| **UPI** (Razorpay Payment Links) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`; webhook → `/payments/razorpay/webhook` | sandbox mock |
| PayPal | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_URL` | sandbox mock |
| Google login | `GOOGLE_CLIENT_IDS` (API) + `extra.googleClientIds` (mobile) | button disabled |
| Apple login | `APPLE_BUNDLE_IDS`, Apple developer account | iOS button errors |
| Phone OTP SMS | `TWILIO_*` or `SMSGATE_*` (free) | code shown on screen in DEBUG |
| Production secrets | `SECRET_KEY`, `SESSION_SECRET`, `DEBUG=false`, `CORS_ORIGINS` | insecure defaults |

**Deploy:** push to GitHub, then on Render choose *New → Blueprint* and pick `render.yaml`.
That creates the database, the API and the website. Update `API_URL` / `PUBLIC_API_URL` if your API URL differs
(step-by-step: `app/store-listing/PLAY_STORE_GUIDE.md`, step 1).

## Publishing the phone app on Google Play

Step-by-step guide: [`app/store-listing/PLAY_STORE_GUIDE.md`](app/store-listing/PLAY_STORE_GUIDE.md).
Store texts, form answers and graphics: [`app/store-listing/`](app/store-listing/).
Android package ID: `com.mayankbhambhu.freshflow`.

What's already in place for Google Play's rules:
* A public privacy policy at `/privacy` on the website, linked from the app's login and profile screens.
* Account deletion in the app (Profile → Delete my account) and on the web (`/account/delete`), via `POST /me/delete`.
  It erases the shopper's personal data and keeps past orders anonymously.
* Only the permissions the app needs: internet, vibration, camera (barcodes, no microphone) and location (store finder).
* On the public server (`render.yaml`) the demo accounts get a secret password (`SEED_PASSWORD`) and aren't listed on the login page.
  The app hides the demo list and server address in store builds.

## Design notes and limits

* Inventory is decremented **when an item enters an in-store smart cart** (as specified) and
  restored if it is removed. Delivery and pickup orders decrement at payment. A production
  system would also expire abandoned in-store carts (a scheduled job calling `DELETE /cart`).
* The WebSocket hub is in-process. To run more than one API instance, add Redis pub/sub
  (the `REDIS_URL` setting is reserved for this).
* Analytics aggregate in Python so the same code runs on SQLite and PostgreSQL. At large
  scale, move them to SQL views or a warehouse; the function signatures stay the same.
* Tables are created with `create_all` on startup. Add Alembic migrations before the first production schema change.
