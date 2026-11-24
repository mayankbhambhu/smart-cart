# Putting FreshFlow on Google Play: step by step

**Package ID:** `com.mayankbhambhu.freshflow`. It can never change after the first upload.
**Copy-and-paste texts and form answers:** [LISTING.md](LISTING.md).

The phone app can't use your laptop as its server once it's on the Play Store, so the backend has
to be online first (step 1). After that come the build and then Play Console.

```
1 Put the backend online (Render) → 2 Expo account → 3 Test APK on your phone
→ 4 Play Console account → 5 Create the app + listing → 6 Build the .aab → 7 Screenshots
→ 8 Internal test → 9 Closed test (12 testers, 14 days) → 10 Production
```

---

## 1. Put the backend online (free, on Render)

1. Sign up at **render.com** with your GitHub account.
2. **New → Blueprint**, pick the `smart-cart` repository. Render reads `render.yaml` and creates the
   database, the API (`freshflow-api`) and the website (`freshflow-web`: one address for shoppers,
   store staff and admins).
3. When it asks for **SUPPORT_EMAIL**, type the email you want on the privacy policy.
4. Wait until all three say **Live** or **Available** (the first build takes a few minutes).
5. Open `freshflow-api` and `freshflow-web` and note their addresses. If a name was taken, Render adds
   letters, e.g. `freshflow-api-x7k2.onrender.com`. If an address differs from `render.yaml`, replace
   the old address in `render.yaml` and in `app/eas.json` with the real one, commit and push.
6. Check: open `https://<api address>/health`. It should show `"status":"ok"`.
7. The demo accounts' password is **not** `Password@123` online. Find it in Render → `freshflow-api`
   → **Environment** → `SEED_PASSWORD` (click the eye icon).
8. If you use Google sign-in, email links, SSO or SMS, copy those keys from your `backend/api/.env` into
   Render → `freshflow-api` → **Environment** too. In Firebase → Authentication → Settings →
   **Authorized domains**, add your website's address.

> Free plan: services sleep after about 15 minutes without visitors (the next visit takes about a minute to
> wake up), and the free database expires after 30 days. That's fine for testing; upgrade the plans in
> `render.yaml` before real customers use it.

## 2. Make an Expo account and link the project

Sign up at **expo.dev** (free). Then, on your Mac:

```bash
cd ~/Desktop/smart-cart/app
```
```bash
npx eas-cli@latest login
```
```bash
npx eas-cli@latest init
```
`init` adds a `projectId` to `app.json`. Commit and push that change.

## 3. Build a test version and try it on your phone

```bash
npx eas-cli@latest build -p android --profile preview
```
- It asks to create an **Android keystore**: answer **Yes**. Expo keeps it safe for you. It's the key
  that proves future updates come from you.
- The build runs in Expo's cloud (10–20 minutes; the free plan has a monthly build limit and a queue).
- At the end you get a link. Open it **on your Android phone**, download the `.apk` and install it
  (allow "install unknown apps" when asked).
- Test everything: sign in, shop, Scan & Go, pay, receipt, family list, store finder, Profile → Privacy
  policy, and Profile → Delete my account (with a throwaway account).

## 4. Create your Google Play developer account

1. Go to **play.google.com/console** and sign up as a **Personal** account.
2. Pay the one-time **US$25** fee.
3. Verify your identity (government ID) and your phone number.
4. Google may also ask you to install the **Play Console** app on an Android phone to prove you have one.

Verification can take a few days, so start this early.

## 5. Create the app and fill in the listing

1. Play Console → **Create app**. App name `FreshFlow`, default language English (India), **App**, **Free**.
   Accept the declarations.
2. **Store listing**: paste the texts from `LISTING.md` and upload `icon-512.png` and `feature-graphic.png`.
3. **Policy → App content**: complete every section using `LISTING.md` (privacy policy, ads, app access,
   content rating, target audience, data safety…). Play Console shows a checklist of what's missing.

## 6. Build the Play Store version (.aab)

```bash
npx eas-cli@latest build -p android --profile production
```
This makes an **Android App Bundle** (`.aab`), the format Play requires. The version number goes up
by itself on every production build. Download the `.aab` from the link at the end.

## 7. Take the screenshots

Play needs at least **2 phone screenshots** (up to 8). With the test APK from step 3 on your phone,
take screenshots of, for example:
1. The Shop screen with products
2. Scan & Go with the store route
3. A family list
4. The cart / checkout
5. A receipt QR code

Sign in as the demo shopper so no real personal data appears. Upload them in **Store listing**.

## 8. Internal testing (just you)

1. Play Console → **Test and release → Testing → Internal testing → Create new release**.
2. Upload the `.aab` from step 6. The **first upload must be done by hand** in Play Console like this.
3. Play asks about **Play App Signing**: accept. Google signs the final app; your Expo key is the "upload key".
4. Add yourself as a tester (your Gmail), save, and **roll out**. Open the opt-in link on your phone and
   install FreshFlow from the Play Store.

## 9. Closed testing: 12 testers for 14 days

New personal developer accounts must run a **closed test with at least 12 testers who stay opted in for
14 days in a row** before they can apply for production. Check Play Console for the current numbers.

1. **Testing → Closed testing → Create track**, upload the same `.aab` (or a newer one), add your testers'
   Gmail addresses (classmates, family), and roll out.
2. Send them the opt-in link. They must **install the app and keep it** for the full 14 days.
3. Fix any problems they report: build again (step 6) and upload the new `.aab` to the same track.

> For a capstone, this closed test is usually enough: real people install FreshFlow from Google Play,
> and you don't have to publish a store that isn't really selling groceries.

## 10. Production (public)

After the 14 days, Play Console shows **Apply for production**. Answer the questions about your test, then
create a production release. Google reviews it, which usually takes a few days.

Before going public with real customers:
- Switch payments to real ones: `PAYMENTS_MODE=live` with your Stripe / Razorpay / PayPal keys. In mock mode,
  "Pay" doesn't charge anything.
- Upgrade the Render plans (see step 1).
- Real stores and products: the demo stores are sample data.

---

## Google sign-in on the Play Store app (optional)

Google sign-in on Android checks the app's signing certificate:
1. Play Console → **Test and release → App integrity → App signing**. Copy the **SHA-1** of the
   *App signing key certificate*.
2. Google Cloud → **APIs & Services → Credentials → Create credentials → OAuth client ID → Android**.
   Package name `com.mayankbhambhu.freshflow`, paste the SHA-1.
3. Repeat with the SHA-1 of your **upload key** (run `npx eas-cli@latest credentials` → Android →
   production) so the test APK works too.
4. Put the Android client ID in `app/eas.json` under `build → base → env` as
   `"EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID": "…"`, plus `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (your web
   client ID), then build again.

## Updating the app later

1. Make your changes and test them with Expo Go.
2. `npx eas-cli@latest build -p android --profile production`
3. Upload the new `.aab` in Play Console (or use `npx eas-cli@latest submit -p android` once you've set
   up a Google service account; see Expo's "Submit to the Google Play Store" docs).
