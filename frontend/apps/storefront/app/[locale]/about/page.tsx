import { notFound } from "next/navigation";

import { getStorefrontContext } from "@/lib/theme";

export default async function AboutPage() {
  const context = await getStorefrontContext();
  if (!context) notFound();

  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-2xl font-semibold">{context.store.name}</h1>
    </div>
  );
}
