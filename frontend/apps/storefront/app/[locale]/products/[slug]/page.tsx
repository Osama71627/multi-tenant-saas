import { notFound } from "next/navigation";

import { ProductDetail } from "@/components/product-detail";
import { getProduct } from "@/lib/catalog";
import { currentHostname, getStorefrontContext } from "@/lib/theme";

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { slug } = await params;
  const context = await getStorefrontContext();
  if (!context) notFound();

  const hostname = await currentHostname();
  const product = await getProduct(hostname, slug);
  if (!product) notFound();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <ProductDetail product={product} />
    </div>
  );
}
