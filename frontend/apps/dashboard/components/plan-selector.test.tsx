import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlanSelector } from "./plan-selector";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));

// `@/lib/api-client` exports a SINGLETON openapi-fetch client, created
// via `createClient({ baseUrl: "/api/bff" })` -- which captures
// `globalThis.fetch` as a default parameter AT MODULE-IMPORT TIME
// (`fetch: baseFetch = globalThis.fetch` in openapi-fetch's own
// source), before any per-test `vi.stubGlobal("fetch", ...)` could run,
// and calls it with a constructed `Request` object rather than a plain
// URL string. Mocking `global.fetch` (the pattern
// components/login-form.test.tsx uses for its own plain `fetch` calls)
// therefore does not work here -- mocking the module boundary itself
// is the correct level for anything going through this client.
const getMock = vi.fn();
const postMock = vi.fn();
const patchMock = vi.fn();
vi.mock("@/lib/api-client", () => ({
  api: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
  },
}));

const PLANS = [
  {
    id: "plan-basic",
    plan_code: "basic",
    plan_name: "Basic",
    price_monthly: 9900,
    price_yearly: 99000,
    currency: "SAR",
    features: [{ feature_key: "api_access", enabled: false }],
    quotas: [{ quota_key: "products", limit: 50 }],
  },
  {
    id: "plan-pro",
    plan_code: "professional",
    plan_name: "Professional",
    price_monthly: 19900,
    price_yearly: 199000,
    currency: "SAR",
    features: [{ feature_key: "api_access", enabled: true }],
    quotas: [{ quota_key: "products", limit: 500 }],
  },
];

const PRESETS = [
  {
    id: "preset-fashion",
    name: "Fashion Default",
    default_settings: { primary_color: "#111", secondary_color: "#222", accent_color: "#333" },
    preview_image_url: "",
    theme_code: "fashion",
    theme_name: "Fashion",
    theme_category: "Fashion & Apparel",
  },
];

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  patchMock.mockReset();
  push.mockReset();
  replace.mockReset();
});

function stubReadEndpoints(session: { status: number; data?: unknown }) {
  getMock.mockImplementation((path: string) => {
    if (path.includes("checkout-sessions/current")) {
      return Promise.resolve(
        session.status === 404
          ? { data: undefined, error: undefined, response: { status: 404 } }
          : { data: session.data, error: undefined, response: { status: 200 } }
      );
    }
    if (path.includes("plans/public")) {
      return Promise.resolve({ data: PLANS, error: undefined, response: { status: 200 } });
    }
    if (path.includes("themes/public/presets")) {
      return Promise.resolve({ data: PRESETS, error: undefined, response: { status: 200 } });
    }
    throw new Error(`Unexpected GET ${path}`);
  });
}

describe("PlanSelector", () => {
  it("redirects straight to the theme marketplace when no theme is known -- no dead-end screen", async () => {
    stubReadEndpoints({ status: 404 });

    renderWithClient(<PlanSelector locale="en" themePresetIdFromUrl={null} />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en/themes"));
    expect(screen.queryByText("Professional")).not.toBeInTheDocument();
  });

  it("starts a session from the URL theme, then renders real plans from the backend", async () => {
    stubReadEndpoints({ status: 404 });
    postMock.mockResolvedValue({
      data: {
        id: "session-1",
        theme_preset_id: "preset-fashion",
        plan_version: null,
        checkout_status: "draft",
        payment_status: "not_started",
        provisioning_status: "not_started",
      },
      error: undefined,
    });

    renderWithClient(<PlanSelector locale="en" themePresetIdFromUrl="preset-fashion" />);

    // The theme card renders once the session (POSTed with the URL's
    // theme id) resolves and the matching preset is found locally.
    expect(await screen.findByText("Fashion")).toBeInTheDocument();
    expect(screen.getByText("Fashion & Apparel")).toBeInTheDocument();

    // Real, dynamic plan data -- never hardcoded in the component.
    expect(await screen.findByText("Professional")).toBeInTheDocument();
    expect(screen.getByText("SAR 199.00")).toBeInTheDocument(); // 19900 minor units

    expect(postMock).toHaveBeenCalledWith(
      "/api/v1/subscriptions/checkout-sessions/current",
      expect.objectContaining({ body: { theme_preset_id: "preset-fashion" } })
    );
  });

  it("selecting a plan PATCHes only a plan_version_id, never a price", async () => {
    const user = userEvent.setup();
    stubReadEndpoints({ status: 404 });
    postMock.mockResolvedValue({
      data: {
        id: "session-1",
        theme_preset_id: "preset-fashion",
        plan_version: null,
        checkout_status: "draft",
        payment_status: "not_started",
        provisioning_status: "not_started",
      },
      error: undefined,
    });
    patchMock.mockImplementation((_path: string, options: { body: Record<string, unknown> }) => {
      expect(Object.keys(options.body)).toEqual(["plan_version_id"]); // never a price field
      return Promise.resolve({
        data: {
          id: "session-1",
          theme_preset_id: "preset-fashion",
          plan_version: PLANS[1],
          checkout_status: "ready_for_payment",
          payment_status: "not_started",
          provisioning_status: "not_started",
        },
        error: undefined,
      });
    });

    renderWithClient(<PlanSelector locale="en" themePresetIdFromUrl="preset-fashion" />);

    const professionalCard = (await screen.findByText("Professional")).closest(
      '[class*="rounded-xl"]'
    ) as HTMLElement;
    await user.click(within(professionalCard).getByText("selectPlan"));

    await waitFor(() => expect(screen.getByText("continueToPayment")).toBeInTheDocument());
    expect(patchMock).toHaveBeenCalledWith(
      "/api/v1/subscriptions/checkout-sessions/current",
      expect.objectContaining({ body: { plan_version_id: "plan-pro" } })
    );
  });

  it("Continue to payment navigates to the dedicated subscription checkout page", async () => {
    const user = userEvent.setup();
    stubReadEndpoints({
      status: 200,
      data: {
        id: "session-1",
        theme_preset_id: "preset-fashion",
        plan_version: PLANS[1],
        checkout_status: "ready_for_payment",
        payment_status: "not_started",
        provisioning_status: "not_started",
      },
    });

    // No `?theme=` this time -- a bare revisit of a session that already
    // has a plan selected, not a fresh arrival from the marketplace.
    renderWithClient(<PlanSelector locale="en" themePresetIdFromUrl={null} />);

    await user.click(await screen.findByText("continueToPayment"));

    // The actual payment form/summary lives on /subscription/checkout
    // (subscription-checkout.tsx), not here -- this page's only job
    // past plan-selection is to send the user there.
    expect(push).toHaveBeenCalledWith("/en/subscription/checkout");
    expect(postMock).not.toHaveBeenCalled();
  });

  it("a session already past plan-selection redirects straight to subscription checkout", async () => {
    stubReadEndpoints({
      status: 200,
      data: {
        id: "session-1",
        theme_preset_id: "preset-fashion",
        plan_version: PLANS[1],
        checkout_status: "payment_pending",
        payment_status: "pending",
        provisioning_status: "not_started",
      },
    });

    renderWithClient(<PlanSelector locale="en" themePresetIdFromUrl={null} />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en/subscription/checkout"));
  });
});
