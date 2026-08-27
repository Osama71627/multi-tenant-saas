import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LandingPage from "./page";

// Mirrors the `useTranslations` mock pattern already established for
// client components (apps/platform-admin/components/login-form.test.tsx)
// -- here for the server-side `getTranslations` this async Server
// Component actually calls. Returning the key itself is enough to
// assert routing/structure without depending on copy wording.
vi.mock("next-intl/server", () => ({
  getTranslations: async () => (key: string) => key,
}));

describe("LandingPage", () => {
  it("routes both primary CTAs to registration and the secondary CTA to the themes placeholder", async () => {
    const jsx = await LandingPage({ params: Promise.resolve({ locale: "en" }) });
    render(jsx);

    const createStoreLinks = screen.getAllByRole("link", { name: "hero.primaryCta" });
    expect(createStoreLinks.length).toBeGreaterThanOrEqual(2); // header CTA + hero CTA
    for (const link of createStoreLinks) {
      expect(link).toHaveAttribute("href", "/en/register");
    }

    const exploreThemesLink = screen.getByRole("link", { name: "hero.secondaryCta" });
    expect(exploreThemesLink).toHaveAttribute("href", "/en/themes");

    const logInLink = screen.getByRole("link", { name: "logIn" });
    expect(logInLink).toHaveAttribute("href", "/en/login");
  });

  it("localizes every CTA and nav link to the requested locale", async () => {
    const jsx = await LandingPage({ params: Promise.resolve({ locale: "ar" }) });
    render(jsx);

    expect(screen.getAllByRole("link", { name: "hero.primaryCta" })[0]).toHaveAttribute(
      "href",
      "/ar/register"
    );
    expect(screen.getByRole("link", { name: "hero.secondaryCta" })).toHaveAttribute(
      "href",
      "/ar/themes"
    );
  });
});
