<div align="center">

<img src="app/store-listing/icon-512.png" alt="FreshFlow logo" width="96">

# FreshFlow

**Shop. Scan. Walk out.**

Grocery delivery and store pickup, plus **checkout-free in-store shopping**,
with the tools a supermarket needs to run itself.

Python (FastAPI) · Website (Jinja2 + htmx) · iOS & Android app (React Native / Expo) · PostgreSQL or SQLite

</div>

---

Picture a Saturday evening at the supermarket: you hunt for items, then wait in a long billing queue.
FreshFlow removes both problems:

> Your family's shared list turns into the **shortest walk through the aisles** ("Aisle 4, Row 2") →
> you **scan items with your phone** as you shop → you **pay on your phone** (UPI, cards, Google Pay,
> Apple Pay, PayPal) → you show a **QR receipt at the exit gate** and walk out. No queue, no cashier.

Every scan also updates the store's **live inventory**. The same system gives owners, managers and staff
their daily tools: tasks, restock alerts, shifts, attendance and sales reports. Admins run the whole platform.

<p align="center">
  <img src=".github/readme/scan-and-go.png" alt="Scan & Go: aisle route through the store and smart cart" width="900">
</p>

## Contents

- [What's inside](#whats-inside)
- [Features](#features)
- [Screenshots](#screenshots)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Sign-in options](#sign-in-options)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Phone app: today and next](#phone-app-today-and-next)
- [Security and privacy](#security-and-privacy)
- [Design notes and limits](#design-notes-and-limits)

## What's inside

| Part | Who uses it | Local address | Code |
|---|---|---|---|
| **API** (REST + WebSocket) | the website and the app | http://localhost:8000/docs | `backend/api/` |
| **Website**: one address, one login page | everyone | http://localhost:8001 | `backend/web/` + `web/` |
| ↳ Shop | shoppers | `/` | `backend/web/customer/` + `web/customer/` |
| ↳ Store Operations | owner · store manager · floor manager · worker | `/store` | `backend/web/store/` + `web/store/` |
| ↳ Admin | the FreshFlow platform team | `/admin` | `backend/web/admin/` + `web/admin/` |
| **Phone app** (iOS + Android) | everyone | Expo Go | `app/` |

**One login for everybody.** The website and the app have a single login page. After signing in, the
**role on the account** decides what opens: shoppers get the shop, store staff get Store Operations, admins get
Admin. Opening another role's page sends you back to your own, and the API checks the role again on every request.

## Features

### 🛒 For shoppers (website + app)

| Feature | Details |
|---|---|
| **Three ways to shop** | Delivery, **store pickup** (time slots with capacity) or **in-store Scan & Go** |
| **Item locations** | Every product shows its aisle and row, e.g. "Aisle 2, Row 4" |
| **Shortest route** | Your list becomes a walking path through the store: exact aisle-to-aisle distances, then nearest-neighbour + 2-opt optimisation, drawn on an SVG store map |
| **Family lists, live** | Share a list with an invite code. Items added at home appear on the shopper's route instantly |
| **Smart cart** | Scan with the **camera (📷)** or type. Stock leaves the shelf count the moment an item is in your cart. Change quantities with − / + or remove with ✕, and the stock goes back |
| **Running total** | Subtotal, offers, GST and total update with every scan |
| **Pay on your phone** | Stripe (cards, Apple Pay, Google Pay), Razorpay UPI, PayPal. A sandbox mode needs no accounts |
| **Exit-gate receipt** | A signed QR code. The gate verifies it in a second, and a copied or reused receipt is rejected |
| **Stores & stock check** | Find nearby stores and check stock before leaving home. **Add** straight from the results |
| **Profile** | Saved payment methods (tokenised), dietary preferences that filter the catalogue, purchase history, privacy policy, **delete my account** |

### 🏪 For store teams (Store Operations)

| Feature | Who |
|---|---|
| **Live inventory**: below its threshold an item raises a restock alert and **auto-assigns** a task to the least-busy worker | all staff |
| **Business analysis**: net sales, gross profit and margin, profit after staff cost, best sellers, best offers, **rush hours**, category mix, low and dead stock, for today / week / month / year / any range | owner, store manager |
| **Work & reviews**: assign → employee alerted live → done **with a report** → manager rates it ★1–5 | managers, floor managers |
| **Shifts and attendance**: weekly rota, clock in/out, hours worked, wages earned | supervisors |
| **Hiring chain**: store manager requests a new employee → **owner** approves → **admin** issues the login | store manager, owner |
| Orders (pickup/delivery status), **exit-gate scanner** (camera), offers, support tickets | as appropriate |

### 🛡️ For admins

- Approve credential requests and **issue logins** (temporary password, changed at first sign-in)
- **Offboard employees**: login revoked at once, open tasks flagged, attendance kept for payroll
- All **stores** with owners, employees, wages and monthly KPIs; onboard new stores
- **Store issues** (support tickets) and a platform-wide sales overview

## Screenshots

| One login for everyone | Shop |
|---|---|
| <img src=".github/readme/login.png" alt="Login page" width="380"> | <img src=".github/readme/shop.png" alt="Shop" width="520"> |

| Store Operations: business analysis | Admin: platform overview |
|---|---|
| <img src=".github/readme/store-analytics.png" alt="Store analytics" width="460"> | <img src=".github/readme/admin.png" alt="Admin overview" width="460"> |

## How it works

```mermaid
flowchart LR
    subgraph Clients
        A["📱 Phone app<br/>(Expo, iOS + Android)"]
        W["🌐 Website<br/>shop · /store · /admin"]
        G["🚪 Exit gate<br/>(QR check)"]
    end
    subgraph Backend["backend/ (Python)"]
        WEB["backend/web<br/>FastAPI + Jinja2"]
        API["backend/api<br/>FastAPI REST + WebSocket"]
    end
    DB[("PostgreSQL / SQLite")]
    EXT["Stripe · Razorpay UPI · PayPal<br/>Google · Firebase · SSO · Twilio / SMS gateway"]

    W --> WEB --> API
    A -- "HTTPS + JWT" --> API
    G -- "X-Gate-Key" --> API
    API --> DB
    API --> EXT
    API -. "live updates (WebSocket)" .-> A
    API -. "live updates (WebSocket)" .-> W
```

- **Auth:** JWT bearer tokens. Passwords hashed with bcrypt, OTP codes stored only as hashes.
- **Roles:** `customer`, `worker`, `floor_manager`, `store_manager`, `owner`, `admin`. Staff only ever see their own store.
- **Real time:** a WebSocket hub with channels `list:<id>`, `store:<id>`, `user:<id>` and `admin` for family lists, inventory, restock alerts, tasks, gate events and notifications.
- **Payments:** the server always re-checks with the payment provider before issuing a receipt. `PAYMENTS_MODE=mock` runs the whole flow without provider accounts.
- **Exit gate:** a receipt code looks like `FF1.<order>.<nonce>.<HMAC>`. Forged codes are rejected before any database lookup, and each code is single-use, tied to one store, and expires.

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.13, **FastAPI**, **SQLAlchemy 2.0**, Pydantic v2, PyJWT, bcrypt, WebSockets |
| Website | **FastAPI + Jinja2** server-rendered pages, **htmx**, Chart.js, html5-qrcode (camera scanning) |
| Phone app | **React Native + Expo SDK 58**, Expo Router, TypeScript, expo-camera, Stripe React Native |
| Database | PostgreSQL (production) or SQLite (development) |
| Payments | Stripe, Razorpay (UPI), PayPal, plus a built-in sandbox mode |
| Sign-in | Email + password, phone OTP (Twilio Verify or a free Android SMS gateway), Google, Firebase email link, OpenID Connect SSO, Sign in with Apple |
| Deploy | Render Blueprint (`render.yaml`), Docker Compose |

## Project structure

Three main folders: **`backend/`** (all Python server code), **`web/`** (the website's pages, styles and scripts)
and **`app/`** (the phone app). The website and the app both use the same API.

```
smart-cart/
├── backend/                       ══ BACKEND (Python) ══
│   ├── api/                       the REST + WebSocket API, used by the website AND the app
│   │   ├── app/
│   │   │   ├── main.py            app factory, routers, CORS
│   │   │   ├── seed.py            demo data: 3 stores, 51 products, staff, months of sales
│   │   │   ├── core/              settings, database, security, role guards, WebSocket hub, phone numbers
│   │   │   ├── models/            SQLAlchemy models: users, stores, catalogue, carts & lists, orders, staff, support
│   │   │   ├── schemas/           Pydantic request/response models
│   │   │   ├── services/          routing (aisle route), inventory, pricing, payments, orders,
│   │   │   │                      analytics, sign-in providers, SSO, notifications
│   │   │   └── api/routes/        auth, stores, lists, cart, orders, gate, store_ops, people,
│   │   │                          analytics, support, admin, ws
│   │   ├── tests/                 pytest: 33 tests (SQLite or PostgreSQL)
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── web/                       the website's server side
│       ├── main.py                one website: shop at /, Store Operations at /store, Admin at /admin
│       ├── shared/                API client, sign-in session, the one login page (signin.py)
│       ├── customer/app.py        shop, cart, Scan & Go, lists, stores, orders, profile, barcode sheet
│       ├── store/app.py           overview, tasks, inventory, orders, gate, shifts, attendance, team, analysis…
│       ├── admin/app.py           overview, requests, stores, employees, tickets
│       ├── requirements.txt
│       └── Dockerfile
│
├── web/                           ══ WEBSITE PAGES (HTML, CSS, JS) ══
│   ├── shared/templates/          layout, login page, privacy policy, email-link page
│   ├── shared/static/             app.css, live.js, vendored htmx / Chart.js / html5-qrcode
│   ├── customer/templates/        shop pages
│   ├── store/templates/           Store Operations pages
│   └── admin/templates/           admin pages
│
├── app/                           ══ PHONE APP (Expo, TypeScript) ══
│   ├── src/app/                   screens: login, (tabs) shopper app, staff/, admin/, cart, scan, stores…
│   ├── src/components/            UI kit, product card, store map, offline QR code
│   ├── src/lib/                   API client, auth, roles, sign-in, cart, live updates, payments
│   ├── store-listing/             Google Play texts, graphics and step-by-step guide (for later)
│   ├── app.json · eas.json        app settings and build profiles
│   └── package.json
│
├── scripts/
│   ├── dev.sh                     start everything locally (creates the venv, seeds demo data)
│   └── smoke_test.py              end-to-end test of every page and role
├── .env.example                   every setting, documented
├── render.yaml                    one-click cloud deploy (database + API + website)
└── docker-compose.yml             PostgreSQL + API + website in Docker
```

## Getting started

### What you need
- **Python 3.11+** (3.13 recommended)
- **Node.js LTS**, only for the phone app
- The free **Expo Go** app on your phone (App Store / Play Store), only for the phone app

### 1. Get the code
```bash
git clone https://github.com/mayankbhambhu/smart-cart.git
```
```bash
cd smart-cart
```

### 2. Start the API and the website
```bash
./scripts/dev.sh
```
The first run creates a Python virtual environment, installs everything and fills an SQLite database with demo data.
Then open **http://localhost:8001**.

### 3. Sign in with a demo account
Every demo account uses the password **`Password@123`**.

| Account | Opens |
|---|---|
| `asha@example.com`, `rohan@example.com` (they share the *Verma Family Weekly* list) | Shop |
| `owner.blr01@freshflow.app`, `manager.blr01@…`, `floor1.blr01@…`, `worker1.blr01@…` (also `blr02`, `mum01`) | Store Operations |
| `admin@freshflow.app` | Admin |

To start over with fresh demo data (stop the servers first):
```bash
cd backend/api && ../../.venv/bin/python -m app.seed --reset && cd ../..
```

### 4. Try the headline flow
1. Sign in as **Rohan** → **Scan & Go** → pick a store. You'll see your family list as a route through the aisles.
2. In a second browser, sign in as **Asha** and add "Curd" to the family list. Rohan's route updates live.
3. Scan items with **📷**. Open the **demo barcode sheet** (link under the camera, or `/barcodes`) on another screen, or print it.
4. **Checkout** → **Pay**.
5. Sign in as `worker1.blr01@freshflow.app`, go to **Exit gates**, and scan or paste the receipt code. 🟢 Gate open.
   Re-scanning within 2 minutes is allowed (the shopper tapped twice); reusing the receipt later is rejected.

### 5. Run the phone app (Expo Go)
Keep `./scripts/dev.sh` running. In a **second terminal**:
```bash
cd app
```
```bash
npm install
```
```bash
npx expo start
```
Scan the QR code with the **Camera app** (iPhone) or inside **Expo Go** (Android). The phone and the computer must be on the
**same Wi-Fi**; the app finds the API on your computer by itself.

<details>
<summary>The app can't connect?</summary>

- Check both devices are on the same Wi-Fi.
- On macOS, allow incoming connections for Python (System Settings → Network → Firewall).
- Open `http://<your computer's IP>:8000/health` in the phone's browser. It should say `"status":"ok"`.
- The login screen shows the server address the app is using (in development).
</details>

## Sign-in options

The login page offers **email + password**, **phone OTP**, **Sign in with Google**, **email me a sign-in link**
(Firebase), **single sign-on (SSO)** and, on iPhone, **Sign in with Apple**. Each button turns on as soon as its settings
are filled in; until then it says "not set up". Whatever the method, the role on the account decides what opens.

| Method | Who can use it | Settings (in `backend/api/.env`) |
|---|---|---|
| Google | anyone; joins an existing account only if Google says the email is verified | `GOOGLE_WEB_CLIENT_ID` (+ `GOOGLE_IOS_CLIENT_ID`, `GOOGLE_ANDROID_CLIENT_ID` for the app) |
| Email link (Firebase) | anyone; a new email becomes a shopper | `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `EMAIL_LINK_CONTINUE_URL` |
| Phone OTP | anyone; a new number becomes a shopper | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, **or free:** `SMSGATE_USERNAME`, `SMSGATE_PASSWORD` |
| SSO (OpenID Connect) | **existing accounts only** (staff are still created through the hiring chain) | `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_LABEL`, `API_PUBLIC_URL`, `SSO_ALLOWED_REDIRECTS` |

Removed employees are refused by every method. Without any SMS settings, development mode shows the OTP on screen.

<details>
<summary><b>Google</b> setup</summary>

In Google Cloud Console → *APIs & Services → Credentials*, create an OAuth client of type *Web application*. Add the website's
address with nothing after the port (e.g. `http://localhost:8001` and `http://localhost`) under **Authorized JavaScript
origins**. Put the client ID in `GOOGLE_WEB_CLIENT_ID`. For the phone app, also create iOS and Android clients and give the
app their IDs through `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` and
`EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`. Google sign-in in the app needs a development build; it doesn't run inside Expo Go.
</details>

<details>
<summary><b>Email link (Firebase)</b> setup</summary>

Create a Firebase project and add a *Web app* (copy its `apiKey`, `authDomain` and `projectId`). In *Authentication → Sign-in
method → Email/Password*, enable **Email link (passwordless sign-in)**. Under *Authentication → Settings → Authorized
domains*, add the domain of `EMAIL_LINK_CONTINUE_URL` (`localhost` is allowed by default). On a computer the link finishes
sign-in on that page; from the phone app it forwards the link into the app. From a phone, that page must be reachable on an
authorized domain (the deployed website or a tunnel), because a LAN IP address can't be authorized.
</details>

<details>
<summary><b>Phone OTP by SMS</b>: Twilio, or free with your own Android phone</summary>

**Twilio Verify:** create a Twilio account, then in *Verify → Services* create a service with SMS on. Copy the Account SID,
Auth Token and the service SID (`VA…`). Twilio makes, sends and checks the code. A trial account can only text numbers you've
verified in the Twilio console.

**Free: SMS Gateway for Android.** Install the open-source *SMS Gateway for Android* app (sms-gate.app, Android 5+) on a
spare phone with a SIM and an SMS pack. Turn on *Cloud server*, tap *Start*, and copy the username and password it shows into
`SMSGATE_USERNAME` and `SMSGATE_PASSWORD`. FreshFlow makes the code and the phone texts it from its own SIM. For the app's
*Local server* mode, also set `SMSGATE_URL=http://<phone-ip>:8080/message`. Twilio Verify wins if both are set.

Numbers can be typed any way (`98111 11111`, `+91 98111-11111`); they're stored as `+919811111111`, using
`PHONE_DEFAULT_COUNTRY_CODE` for 10-digit numbers.
</details>

<details>
<summary><b>SSO</b> setup</summary>

Register an app with your identity provider (Microsoft Entra ID, Google Workspace, Okta, Auth0, Keycloak…). Set its
redirect URI to `{API_PUBLIC_URL}/auth/sso/callback` (in Google Cloud this goes under *Authorized redirect URIs*, not
JavaScript origins). Copy the issuer URL, client ID and secret into the settings. `OIDC_LABEL` is the button text. The flow
uses authorization code + PKCE, a one-time state and a nonce, and checks the ID token's signature, issuer and audience. Only a
2-minute single-use code goes back to the website or app, never the session token. Return addresses must start with an entry
in `SSO_ALLOWED_REDIRECTS`; remove `exp://` (Expo Go) in production.
</details>

## Configuration

The API's settings live in **`backend/api/.env`** (never committed). [`.env.example`](.env.example) lists and explains
every one. Write values without quotes or spaces around `=`. The rows marked *environment* are read from the environment
instead: on Render, `render.yaml` sets them; locally the defaults are fine.

| Item | Settings | Without it |
|---|---|---|
| Stripe (cards, Apple Pay, Google Pay) | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `PAYMENTS_MODE=live` | sandbox payments |
| UPI (Razorpay Payment Links) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`; webhook → `/payments/razorpay/webhook` | sandbox payments |
| PayPal | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_URL` | sandbox payments |
| Sign-in providers | see [Sign-in options](#sign-in-options) | button shows "not set up" |
| Sign in with Apple | `APPLE_BUNDLE_IDS` and an Apple developer account | iPhone button errors |
| Production secrets | `SECRET_KEY`, `DEBUG=false`, `CORS_ORIGINS`; *environment:* `SESSION_SECRET` (website) | insecure development defaults |
| Demo data on a public server | *environment:* `SEED_PASSWORD` (secret password for demo accounts), `SEED_HISTORY_DAYS` | `Password@123`, 60 days |
| Website | *environment:* `API_URL`, `PUBLIC_API_URL`, `SITE_URL`, `SUPPORT_EMAIL` (shown on `/privacy`) | localhost defaults, generic contact text |

## Testing

```bash
cd backend/api && ../../.venv/bin/python -m pytest -q
```
33 API tests: shopping flows, live lists, Scan & Go → payment → exit gate, store operations, the hiring chain, every
sign-in method (with a fake SSO provider), phone numbers and account deletion. To run them on PostgreSQL, set
`TEST_DATABASE_URL=postgresql://user:pass@localhost/freshflow_test` before the command.

```bash
.venv/bin/python scripts/smoke_test.py
```
End-to-end test against the running servers (`./scripts/dev.sh`). It signs in as every role, checks each lands in the right
section and can't open the others, opens every page, and runs Scan & Go → pay → exit gate.

```bash
cd app && npx tsc --noEmit
```
Type-checks the phone app.

## Deployment

**Render (free plan):** push to GitHub, then on [render.com](https://render.com) choose **New → Blueprint** and pick this
repository. `render.yaml` creates the database, the API (`freshflow-api`) and the website (`freshflow-web`). The demo data is
created on first start with a secret `SEED_PASSWORD` (see it in Render → freshflow-api → Environment). If Render gives a
service a different address, update the addresses in `render.yaml` and `app/eas.json`.

> Free Render services sleep after about 15 minutes without visitors (the next visit takes about a minute), and a free
> database expires after 30 days. Upgrade the plans in `render.yaml` for real use.

**Docker:**
```bash
docker compose up --build
```
This runs PostgreSQL, the API and the website (http://localhost:8001). Then add the demo data:
```bash
docker compose exec api python -m app.seed
```

## Phone app: today and next

**Today:** the iOS and Android app runs in **Expo Go**. Shopping, Scan & Go with the camera, family lists, routes, receipts,
sandbox payments, and the store and admin sections all work there.

**Next:** publishing to Google Play and the App Store. The groundwork is ready:
- package ID `com.mayankbhambhu.freshflow`, app icon and splash screen
- build profiles in `eas.json`
- store texts and graphics, plus a step-by-step guide, in [`app/store-listing/`](app/store-listing/PLAY_STORE_GUIDE.md)

Real Apple Pay / Google Pay, Google sign-in and Sign in with Apple need a development or store build
(`npx eas-cli build`), not Expo Go.

## Security and privacy

- **Account deletion:** shoppers can delete their account in the app (Profile → Delete my account) or on the web
  (`/account/delete`). Personal data is erased; past orders are kept without personal details for tax records.
- **Privacy policy** at `/privacy`, linked from the login and profile screens.
- **Role checks everywhere:** the website, the app and the API each check the role; staff only see their own store.
- **No card numbers stored:** only the payment provider's token and a label like "Visa •••• 4242".
- **Hashed secrets:** passwords with bcrypt; OTP and single-use sign-in codes stored only as hashes.
- **Signed exit-gate receipts** that can't be forged or reused.
- **Few phone permissions:** internet, camera (barcodes only, no microphone) and location (store finder only).
- **Secrets stay out of git:** `backend/api/.env` is ignored; a public server uses a secret demo password.

## Design notes and limits

- In Scan & Go, stock leaves the shelf count **when an item enters the cart** and returns if it's removed. Delivery and
  pickup orders reduce stock at payment. A production system would also clear abandoned in-store carts with a scheduled job.
- The WebSocket hub runs inside one API process. To run several API servers, add Redis pub/sub (`REDIS_URL` is reserved).
- Analytics are computed in Python so the same code runs on SQLite and PostgreSQL; at large scale, move them to SQL views.
- Tables are created on startup. Add Alembic migrations before the first production schema change.
- The demo products use made-up EAN-13 barcodes; use the demo barcode sheet (`/barcodes`) to try scanning.

---

<div align="center">
Built as a capstone project for <b>Python Application Programming</b>.
</div>
