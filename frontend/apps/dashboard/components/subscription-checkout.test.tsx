import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SubscriptionCheckout } from "./subscription-checkout";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));

// Same module-boundary mock plan-selector.test.tsx already established
// -- see that file's own comment for why `vi.stubGlobal("fetch", ...)`
// doesn't work against the shared openapi-fetch client.
const getMock = vi.fn();
const postMock = vi.fn();
vi.mock("@/lib/api-client", () => ({
  api: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
  },
}));

const PLAN = {
  id: "plan-pro",
  plan_code: "professional",
  plan_name: "Professional",
  price_monthly: 19900,
  price_yearly: 199000,
  currency: "SAR",
  features: [{ feature_key: "api_access", enabled: true }],
  quotas: [{ quota_key: "products", limit: 500 }],
};

const PRESETS = [
  {
    id: "preset-fashion",
    name: "Fashion Default",
    default_settings: { primary_color: "#111" },
    preview_image_url: "",
    theme_code: "fashion",
    theme_name: "Fashion",
    theme_category: "Fashion & Apparel",
  },
];

function session(overrides: Record<string, unknown>) {
  return {
    id: "session-1",
    theme_preset_id: "preset-fashion",
    plan_version: PLAN,
    checkout_status: "ready_for_payment",
    payment_status: "not_started",
    provisioning_status: "not_started",
    ...overrides,
  };
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  push.mockReset();
  replace.mockReset();
});

function stubGet(currentSession: Record<string, unknown> | null, intent: Record<string, unknown> | null = null) {
  getMock.mockImplementation((path: string) => {
    if (path.includes("payment-intent")) {
      return Promise.resolve(
        intent
          ? { data: intent, error: undefined, response: { status: 200 } }
          : { data: undefined, error: undefined, response: { status: 404 } }
      );
    }
    if (path.includes("checkout-sessions/current")) {
      return Promise.resolve(
        currentSession
          ? { data: currentSession, error: undefined, response: { status: 200 } }
          : { data: undefined, error: undefined, response: { status: 404 } }
      );
    }
    if (path.includes("themes/public/presets")) {
      return Promise.resolve({ data: PRESETS, error: undefined, response: { status: 200 } });
    }
    throw new Error(`Unexpected GET ${path}`);
  });
}

describe("SubscriptionCheckout", () => {
  it("renders the real plan/theme/price summary and Pay Now initiates a payment with the card number only", async () => {
    const user = userEvent.setup();
    stubGet(session({}));
    postMock.mockResolvedValue({
      data: { id: "intent-1", amount: 19900, currency: "SAR", state: "pending", failure_reason: "" },
      error: undefined,
    });

    renderWithClient(<SubscriptionCheckout locale="en" email="merchant@example.com" fullName="Merchant Name" />);

    expect(await screen.findByText("Professional")).toBeInTheDocument();
    expect(screen.getByText("Fashion")).toBeInTheDocument();
    expect(screen.getAllByText("SAR 199.00").length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("merchant@example.com")).toBeInTheDocument();

    await user.type(screen.getByLabelText("paymentMethod.cardNumber"), "4242 4242 4242 4242");
    await user.type(screen.getByLabelText("paymentMethod.expiry"), "12/30");
    await user.type(screen.getByLabelText("paymentMethod.cvc"), "123");
    await user.click(screen.getByText("paymentMethod.payNow"));

    await waitFor(() =>
      expect(postMock).toHaveBeenCalledWith(
        "/api/v1/subscriptions/checkout-sessions/current/pay",
        expect.objectContaining({ body: { card_number: "4242 4242 4242 4242" } })
      )
    );
  });

  it("shows the processing state while the session is payment_pending", async () => {
    stubGet(session({ checkout_status: "payment_pending", payment_status: "pending" }), {
      id: "intent-1",
      amount: 19900,
      currency: "SAR",
      state: "processing",
      failure_reason: "",
    });

    renderWithClient(<SubscriptionCheckout locale="en" email="merchant@example.com" fullName="Merchant Name" />);

    expect(await screen.findByText("processing.title")).toBeInTheDocument();
  });

  it("shows the honest success screen -- Payment Successful / Ready for Business Information -- with no Store-creation UI", async () => {
    stubGet(session({ checkout_status: "awaiting_business_info", payment_status: "paid" }));

    renderWithClient(<SubscriptionCheckout locale="en" email="merchant@example.com" fullName="Merchant Name" />);

    expect(await screen.findByText("success.title")).toBeInTheDocument();
    expect(screen.getByText("success.cta").closest("a")).toHaveAttribute(
      "href",
      "/en/business-info"
    );
  });

  it("shows the failure screen with a retry that starts a NEW payment attempt on the same session, and a way back to plans", async () => {
    const user = userEvent.setup();
    stubGet(
      session({ checkout_status: "payment_failed", payment_status: "failed" }),
      { id: "intent-1", amount: 19900, currency: "SAR", state: "failed", failure_reason: "card_declined" }
    );
    postMock.mockResolvedValue({
      data: { id: "intent-2", amount: 19900, currency: "SAR", state: "pending", failure_reason: "" },
      error: undefined,
    });

    renderWithClient(<SubscriptionCheckout locale="en" email="merchant@example.com" fullName="Merchant Name" />);

    expect(await screen.findByText("failure.title")).toBeInTheDocument();
    expect(screen.getByText("failure.backToPlan").closest("a")).toHaveAttribute("href", "/en/plans");

    await user.type(screen.getByLabelText("paymentMethod.cardNumber"), "4242424242424242");
    await user.type(screen.getByLabelText("paymentMethod.expiry"), "12/30");
    await user.type(screen.getByLabelText("paymentMethod.cvc"), "123");
    await user.click(screen.getByText("paymentMethod.payNow"));

    await waitFor(() =>
      expect(postMock).toHaveBeenCalledWith(
        "/api/v1/subscriptions/checkout-sessions/current/pay",
        expect.objectContaining({ body: { card_number: "4242424242424242" } })
      )
    );
  });

  it("redirects back to /plans when there is no payable session at all", async () => {
    stubGet(null);

    renderWithClient(<SubscriptionCheckout locale="en" email="merchant@example.com" fullName="Merchant Name" />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en/plans"));
  });
});
