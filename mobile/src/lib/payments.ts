import { initPaymentSheet, presentPaymentSheet } from "@stripe/stripe-react-native";
import * as WebBrowser from "expo-web-browser";
import { api } from "./api";
import type { Order, PaymentIntent } from "./types";

/**
 * Runs the right payment UI for the gateway the API chose:
 *  - stripe   : native PaymentSheet (cards + Apple Pay on iOS + Google Pay on Android)
 *  - razorpay : hosted UPI payment page (GPay / PhonePe / Paytm / any UPI app)
 *  - paypal   : PayPal approval page
 *  - mock     : sandbox, no money moves
 * Then asks the API to verify with the gateway and issue the exit receipt.
 */
export async function pay(intent: PaymentIntent): Promise<Order> {
  if (intent.provider === "stripe") {
    const init = await initPaymentSheet({
      merchantDisplayName: "FreshFlow",
      paymentIntentClientSecret: intent.client_secret!,
      applePay: { merchantCountryCode: "IN" },
      googlePay: { merchantCountryCode: "IN", currencyCode: "INR", testEnv: __DEV__ },
      allowsDelayedPaymentMethods: false,
    });
    if (init.error) throw new Error(init.error.message);
    const res = await presentPaymentSheet();
    if (res.error) throw new Error(res.error.code === "Canceled" ? "Payment cancelled" : res.error.message);
  } else if (intent.provider === "razorpay" || intent.provider === "paypal") {
    await WebBrowser.openAuthSessionAsync(intent.approve_url!, "freshflow://payment-complete");
  }
  return api.post<Order>("/payments/confirm", { order_id: intent.order_id });
}
