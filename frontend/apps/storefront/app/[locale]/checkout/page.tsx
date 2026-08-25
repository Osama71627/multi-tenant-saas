"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { formatMoney } from "@/lib/format-money";
import { useCart } from "@/lib/hooks/use-cart";
import { randomUUID } from "@/lib/uuid";
import {
  useCompleteCheckout,
  useInitiatePayment,
  usePaymentProviders,
  useSetCheckoutAddress,
  useSetCheckoutShipping,
  useShippingQuotes,
  useStartCheckout,
} from "@/lib/hooks/use-checkout";

const PROVIDER_LABELS: Record<string, string> = {
  manual_cod: "Cash on delivery",
  stripe: "Card (Stripe)",
  mock: "Mock (testing)",
};

const addressSchema = z.object({
  email: z.string().email(),
  recipient_name: z.string().min(1),
  phone: z.string().min(1),
  country_code: z.string().length(2).toUpperCase(),
  region: z.string(),
  city: z.string().min(1),
  postal_code: z.string(),
  line1: z.string().min(1),
  line2: z.string(),
});
type AddressValues = z.infer<typeof addressSchema>;

type Step = "address" | "shipping" | "payment";

export default function CheckoutPage() {
  const { locale } = useParams<{ locale: string }>();
  const router = useRouter();
  const t = useTranslations("storefront.checkout");
  const { data: cart } = useCart();

  const [step, setStep] = useState<Step>("address");
  const [address, setAddress] = useState<AddressValues | null>(null);
  const [selectedMethodId, setSelectedMethodId] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [placeOrderError, setPlaceOrderError] = useState<string | null>(null);

  const startCheckout = useStartCheckout();
  const setCheckoutAddress = useSetCheckoutAddress();
  const setCheckoutShipping = useSetCheckoutShipping();
  const completeCheckout = useCompleteCheckout();
  const initiatePayment = useInitiatePayment();

  const shippingQuotes = useShippingQuotes({
    country_code: address?.country_code ?? "",
    region: address?.region,
    postal_code: address?.postal_code,
    enabled: step === "shipping",
  });
  const paymentProviders = usePaymentProviders();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AddressValues>({
    resolver: zodResolver(addressSchema),
    defaultValues: {
      email: "",
      recipient_name: "",
      phone: "",
      country_code: "",
      region: "",
      city: "",
      postal_code: "",
      line1: "",
      line2: "",
    },
  });

  async function onSubmitAddress(values: AddressValues) {
    try {
      await startCheckout.mutateAsync();
      await setCheckoutAddress.mutateAsync({
        email: values.email,
        shipping_address: {
          recipient_name: values.recipient_name,
          phone: values.phone,
          country_code: values.country_code,
          region: values.region,
          city: values.city,
          postal_code: values.postal_code,
          line1: values.line1,
          line2: values.line2,
        },
      });
      setAddress(values);
      setStep("shipping");
    } catch {
      // surfaced via setCheckoutAddress.error below
    }
  }

  async function onContinueToPayment() {
    if (!selectedMethodId) return;
    try {
      await setCheckoutShipping.mutateAsync(selectedMethodId);
      setStep("payment");
    } catch {
      // surfaced via setCheckoutShipping.error below
    }
  }

  async function onPlaceOrder() {
    if (!selectedProvider) return;
    setPlaceOrderError(null);
    try {
      const order = await completeCheckout.mutateAsync(randomUUID());
      if (!order) throw new Error("no order returned");
      await initiatePayment.mutateAsync({
        orderId: order.id,
        providerKey: selectedProvider as "mock" | "manual_cod" | "stripe",
        idempotencyKey: randomUUID(),
      });
      const confirmationParams = new URLSearchParams({
        number: order.number,
        total: String(order.total_amount),
        currency: order.currency,
      });
      router.push(`/${locale}/checkout/confirmation?${confirmationParams.toString()}`);
    } catch (err) {
      setPlaceOrderError((err as { detail?: string })?.detail ?? "Could not place your order.");
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-semibold">{t("title")}</h1>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {step === "address" ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("shippingAddress")}</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit(onSubmitAddress)} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="email">{t("email")}</Label>
                    <Input id="email" type="email" {...register("email")} />
                    {errors.email ? (
                      <p className="text-xs text-red-600">{errors.email.message}</p>
                    ) : null}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="recipient_name">{t("recipientName")}</Label>
                    <Input id="recipient_name" {...register("recipient_name")} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="phone">{t("phone")}</Label>
                      <Input id="phone" {...register("phone")} />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="country_code">{t("country")}</Label>
                      <Input id="country_code" placeholder="US" maxLength={2} {...register("country_code")} />
                      {errors.country_code ? (
                        <p className="text-xs text-red-600">{errors.country_code.message}</p>
                      ) : null}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="city">{t("city")}</Label>
                      <Input id="city" {...register("city")} />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="region">{t("region")}</Label>
                      <Input id="region" {...register("region")} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="postal_code">{t("postalCode")}</Label>
                      <Input id="postal_code" {...register("postal_code")} />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="line1">{t("line1")}</Label>
                    <Input id="line1" {...register("line1")} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="line2">{t("line2")}</Label>
                    <Input id="line2" {...register("line2")} />
                  </div>
                  {setCheckoutAddress.isError ? (
                    <p className="text-sm text-red-600">
                      {(setCheckoutAddress.error as { detail?: string })?.detail ??
                        "Could not save your address."}
                    </p>
                  ) : null}
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    style={{ backgroundColor: "var(--sf-primary)" }}
                  >
                    {t("continueToShipping")}
                  </Button>
                </form>
              </CardContent>
            </Card>
          ) : null}

          {step === "shipping" ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("shippingMethod")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {shippingQuotes.isLoading ? (
                  <p className="text-sm text-gray-500">Loading…</p>
                ) : !shippingQuotes.data?.length ? (
                  <p className="text-sm text-gray-500">No shipping options for this address.</p>
                ) : (
                  shippingQuotes.data.map((quote) => (
                    <label
                      key={quote.method_id}
                      className="flex cursor-pointer items-center justify-between rounded-md border px-3 py-2"
                    >
                      <span className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="shipping_method"
                          checked={selectedMethodId === quote.method_id}
                          onChange={() => setSelectedMethodId(quote.method_id)}
                        />
                        {quote.method_name}
                      </span>
                      <span className="text-sm font-medium">
                        {formatMoney(quote.price_amount, quote.currency)}
                      </span>
                    </label>
                  ))
                )}
                {setCheckoutShipping.isError ? (
                  <p className="text-sm text-red-600">
                    {(setCheckoutShipping.error as { detail?: string })?.detail ??
                      "Could not save shipping method."}
                  </p>
                ) : null}
                <Button
                  onClick={onContinueToPayment}
                  disabled={!selectedMethodId || setCheckoutShipping.isPending}
                  style={{ backgroundColor: "var(--sf-primary)" }}
                >
                  {t("continueToPayment")}
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {step === "payment" ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("paymentMethod")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {paymentProviders.isLoading ? (
                  <p className="text-sm text-gray-500">Loading…</p>
                ) : !paymentProviders.data?.length ? (
                  <p className="text-sm text-gray-500">No payment methods available.</p>
                ) : (
                  paymentProviders.data.map((provider) => (
                    <label
                      key={provider.provider_key}
                      className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm"
                    >
                      <input
                        type="radio"
                        name="provider"
                        checked={selectedProvider === provider.provider_key}
                        onChange={() => setSelectedProvider(provider.provider_key)}
                      />
                      {PROVIDER_LABELS[provider.provider_key] ?? provider.provider_key}
                    </label>
                  ))
                )}
                {placeOrderError ? <p className="text-sm text-red-600">{placeOrderError}</p> : null}
                <Button
                  onClick={onPlaceOrder}
                  disabled={
                    !selectedProvider || completeCheckout.isPending || initiatePayment.isPending
                  }
                  style={{ backgroundColor: "var(--sf-primary)" }}
                >
                  {completeCheckout.isPending || initiatePayment.isPending
                    ? t("placingOrder")
                    : t("placeOrder")}
                </Button>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle>{t("orderSummary")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              {cart?.items.map((item) => (
                <div key={item.id} className="flex justify-between">
                  <span className="text-gray-600">
                    {item.variant_sku} × {item.quantity}
                  </span>
                  <span>
                    {formatMoney(item.unit_price_amount * item.quantity, item.currency)}
                  </span>
                </div>
              ))}
              {cart ? (
                <div className="flex justify-between border-t pt-2 font-medium">
                  <span>{t("total")}</span>
                  <span>{formatMoney(cart.subtotal_amount, cart.currency)}</span>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
