import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SetupChecklist } from "./setup-checklist";

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "en" }),
}));

// See plan-selector.test.tsx's identical comment for why the module
// boundary (not global.fetch) is the right level to mock here.
function mockApiGet(storeOverrides: Record<string, unknown> = {}) {
  return (endpoint: string) => {
    if (endpoint === "/api/v1/dashboard/stores/{store_id}") {
      return Promise.resolve({
        data: {
          id: "store-1",
          contact_email: "merchant@example.com",
          primary_domain: "acme.lvh.me",
          ...storeOverrides,
        },
        error: undefined,
      });
    }
    // Every other endpoint SetupChecklist reads (products, inventory
    // balances, shipping zones, payment providers) only needs to
    // resolve to an empty list -- an empty store still exercises the
    // "Preview store" link this test cares about, and an empty
    // `zones` list means the per-zone shipping-methods `useQueries`
    // never fires (`enabled: Boolean(zones?.length)`), so nothing else
    // needs mocking.
    return Promise.resolve({ data: [], error: undefined });
  };
}

vi.mock("@/lib/api-client", () => ({
  api: { GET: (...args: unknown[]) => mockApiGet()(args[0] as string) },
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("SetupChecklist's Preview store link", () => {
  it("opens the merchant's real storefront in a new tab when primary_domain is set", async () => {
    renderWithClient(<SetupChecklist storeId="store-1" />);

    const link = await screen.findByRole("link", { name: "Preview store" });
    // Real bug this guards against: this used to always link to the
    // internal fixture-data preview page regardless of whether the
    // merchant already had a real store -- misleading once real
    // products exist. See setup-checklist.tsx's own comment.
    expect(link).toHaveAttribute("href", "http://acme.lvh.me:4000");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
