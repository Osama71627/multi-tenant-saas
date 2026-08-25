"use client";

import { Monitor, Smartphone } from "lucide-react";
import { useState, type ReactNode } from "react";

type View = "home" | "catalog" | "product" | "cart";

const VIEWS: { key: View; label: string }[] = [
  { key: "home", label: "Home" },
  { key: "catalog", label: "Catalog" },
  { key: "product", label: "Product" },
  { key: "cart", label: "Cart" },
];

/**
 * The only client-side piece of the live-preview page -- everything it
 * renders (`home`/`catalog`/`product`/`cart`) was already rendered
 * SERVER-SIDE by the parent page using the real `@saas/theme-aurora`
 * components; this just switches which pre-rendered panel is visible
 * and how wide the frame is, exactly like a device-preview toggle in a
 * design tool. No second theme renderer.
 */
export function PreviewTabs({
  home,
  catalog,
  product,
  cart,
}: {
  home: ReactNode;
  catalog: ReactNode;
  product: ReactNode;
  cart: ReactNode;
}) {
  const [view, setView] = useState<View>("home");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");

  const panels: Record<View, ReactNode> = { home, catalog, product, cart };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b bg-white px-4 py-2">
        <div className="flex gap-1">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setView(v.key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                view === v.key ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Desktop preview"
            onClick={() => setDevice("desktop")}
            className={`rounded-md p-1.5 ${
              device === "desktop" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            <Monitor className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Mobile preview"
            onClick={() => setDevice("mobile")}
            className={`rounded-md p-1.5 ${
              device === "mobile" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            <Smartphone className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="flex flex-1 justify-center overflow-y-auto bg-gray-100 p-4">
        <div
          className={`h-fit bg-white shadow-sm transition-all ${
            device === "mobile" ? "w-[375px]" : "w-full"
          }`}
        >
          {panels[view]}
        </div>
      </div>
    </div>
  );
}
