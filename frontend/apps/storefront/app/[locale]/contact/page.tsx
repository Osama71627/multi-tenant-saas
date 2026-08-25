import { notFound } from "next/navigation";

import { getStorefrontContext } from "@/lib/theme";

// No contact form here on purpose -- Store.contact_email/contact_phone
// are merchant-only fields (apps/themes/serializers.py:StorefrontStoreSerializer
// deliberately excludes them), and there is no messaging backend for a
// shopper-to-merchant contact form to submit to.
export default async function ContactPage() {
  const context = await getStorefrontContext();
  if (!context) notFound();

  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-2xl font-semibold">{context.store.name}</h1>
    </div>
  );
}
