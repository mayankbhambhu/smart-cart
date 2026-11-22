# FreshFlow: Google Play listing (copy and paste)

Everything you type into Play Console, in the order Play Console asks for it.
Files to upload are in this folder.

## Main store listing  (Grow users → Store presence → Main store listing)

**App name** (max 30 characters)
```
FreshFlow
```

**Short description** (max 80 characters)
```
Groceries in minutes, or Scan & Go in store and skip the checkout queue.
```

**Full description** (max 4000 characters)
```
FreshFlow is grocery shopping your way: get it delivered, pick it up, or shop in the store with Scan & Go and walk straight out, with no checkout queue.

SHOP FOR DELIVERY OR PICKUP
• Browse fruit, vegetables, dairy, staples, snacks and household essentials from stores near you
• Filter by diet: vegan, vegetarian, gluten-free, dairy-free, organic, sugar-free
• Choose a pickup time slot or have it delivered
• Apply offers and see the full price, taxes and fees before you pay

SCAN & GO IN STORE
• Scan barcodes with your phone camera as you shop, and your cart updates instantly
• See exactly where each item is: aisle and row
• Get the shortest walking route through the store for your list
• Watch your running total as you go
• Pay on your phone and show your digital receipt at the exit gate

FAMILY SHOPPING LISTS
• Share a list with your family with an invite code
• Everyone's changes appear live, so if someone adds curd at home, the shopper sees it in the store

STORE FINDER AND STOCK CHECK
• Find stores near you
• Check whether an item is in stock before you go

PAY YOUR WAY
• Cards, Google Pay, UPI and PayPal
• Card numbers are handled by secure payment providers and never stored by FreshFlow

EASY SIGN-IN
• Email and password, phone number with a one-time code, Google, or an email sign-in link

FOR STORE TEAMS
Store staff sign in to the same app to see their tasks, live stock and restock alerts, orders, and to scan receipts at the exit gate. Managers also see sales and team reports.

Your privacy matters: no ads, no selling of your data, and you can delete your account at any time from your profile.
```

**Graphics**
| Field | File |
|---|---|
| App icon (512 × 512) | `icon-512.png` |
| Feature graphic (1024 × 500) | `feature-graphic.png` |
| Phone screenshots (2 to 8) | Take them on your phone (see the guide, step 7) |

**Category:** Shopping
**Contact email:** an email address you check (it's shown publicly on the store page)
**Privacy policy:** `https://<your customer website>/privacy`, e.g. `https://freshflow-shop.onrender.com/privacy`

---

## App content  (Policy → App content)

**Privacy policy:** the `/privacy` link above.

**Ads:** No, my app does not contain ads.

**App access:** "All or some functionality is restricted". Add these instructions:
```
Sign in with email and password.
Shopper: asha@example.com
Store manager: manager.blr01@freshflow.app
Password for both: <the SEED_PASSWORD value from your Render dashboard>
The store staff and admin sections open automatically for staff accounts.
```

**Content rating:** fill in the questionnaire. Category: *All other app types*. Answer **No** to violence,
fear, sexuality, language, drugs, gambling and similar questions. If it asks whether users can interact
or share content, answer **Yes** (family members share shopping lists with people they invite). If it asks
whether users can buy things, say **Yes** (physical groceries).

**Target audience:** 18 and over. **Appeals to children:** No.

**News app:** No.

**Data safety:** see the next section.

**Government app:** No. **Health app:** No.

**Financial features:** the app sells groceries and takes payment through Stripe, Razorpay and PayPal, but it
does not offer banking, loans, wallets or money transfers. Choose the "doesn't provide financial features"
option if Play Console offers it. If you're unsure, read Google's description of each feature on that page.

---

## Data safety form

**Overview questions**
| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | Yes |
| Is all of the user data collected by your app encrypted in transit? | Yes (HTTPS) |
| Do you provide a way for users to request that their data is deleted? | Yes: in the app (Profile → Delete my account) and at `https://<your customer website>/account/delete` |

**Data types**: tick these. For each one: *Collected* = Yes, *Shared* = No (payment, SMS and hosting
providers count as service providers, not sharing), *Processed ephemerally* = No unless stated.

| Data type | Required or optional | Purposes |
|---|---|---|
| Personal info → Name | Required | App functionality, Account management |
| Personal info → Email address | Optional (phone sign-in works without it) | App functionality, Account management |
| Personal info → Phone number | Optional | App functionality, Account management |
| Personal info → Address | Optional (delivery only) | App functionality |
| Personal info → Other info | Optional | App functionality (dietary preferences; for store staff: shifts, attendance, wages) |
| Financial info → User payment info | Optional | App functionality (payments go through Stripe / Razorpay / PayPal) |
| Financial info → Purchase history | Required | App functionality |
| Location → Approximate location | Optional | App functionality (store finder). Processed ephemerally: **Yes** |
| Location → Precise location | Optional | App functionality (store finder). Processed ephemerally: **Yes** |
| App activity → Other user-generated content | Optional | App functionality (shared shopping lists) |

**Don't tick:**
- *Photos and videos*: the camera is only used for barcodes on the phone, and images are never uploaded.
- *Device or other IDs*: none are collected.
- *App interactions / analytics / crash logs*: the app has no analytics or crash-reporting SDK.

If you later add analytics, crash reporting or ads, update this form.
