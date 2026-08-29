"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@saas/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@saas/ui/dialog";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCreateProduct, useUpdateProductStatus } from "@/lib/hooks/use-products";

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const schema = z.object({
  name: z.string().min(1, "Required"),
  slug: z.string().min(1, "Required"),
  sku: z.string().min(1, "Required"),
  price_amount: z.coerce.number().int().min(0, "Must be 0 or more"),
});
type FormValues = z.infer<typeof schema>;

export function AddProductDialog({
  storeId,
  trigger,
}: {
  storeId: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const createProduct = useCreateProduct(storeId);
  const updateStatus = useUpdateProductStatus(storeId);

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", slug: "", sku: "", price_amount: 0 },
  });

  async function onSubmit(values: FormValues) {
    try {
      const product = await createProduct.mutateAsync({
        name: values.name,
        slug: values.slug,
        sku: values.sku,
        price_amount: values.price_amount,
        description: "",
        seo_title: "",
        seo_description: "",
      });
      // apps.catalog.serializers.CreateProductSerializer has no `status`
      // field at all -- POST always creates a Product in the safe,
      // catalog-wide default (Status.DRAFT, apps/catalog/models.py),
      // invisible on this dialog (no status control shown here). A
      // merchant filling in name/SKU/price through THIS quick-add flow
      // has unambiguously already decided to sell it -- real bug found
      // live: they'd create a product, see it in the list, then find
      // setup-checklist.tsx's "At least one active product" step still
      // unchecked with no explanation, since it specifically requires
      // status === "active". Activating right after creation, through
      // the exact same PATCH the manual draft/active/archived dropdown
      // in the products table already uses, closes that gap without
      // touching the backend's own safe default for every OTHER
      // creation path (CSV import, supplier sync -- apps/suppliers --
      // which should stay draft-by-default until a merchant reviews it).
      await updateStatus.mutateAsync({ productId: product.id, status: "active" });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via createProduct.error/updateStatus.error
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Add product</DialogTitle>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              {...register("name")}
              onChange={(e) => {
                setValue("name", e.target.value);
                setValue("slug", slugify(e.target.value));
              }}
            />
            {errors.name ? <p className="text-xs text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="slug">Slug</Label>
            <Input id="slug" {...register("slug")} />
            {errors.slug ? <p className="text-xs text-destructive">{errors.slug.message}</p> : null}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="sku">SKU</Label>
              <Input id="sku" {...register("sku")} />
              {errors.sku ? <p className="text-xs text-destructive">{errors.sku.message}</p> : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price_amount">Price (minor units)</Label>
              <Input id="price_amount" type="number" min={0} {...register("price_amount")} />
              {errors.price_amount ? (
                <p className="text-xs text-destructive">{errors.price_amount.message}</p>
              ) : null}
            </div>
          </div>

          {createProduct.isError || updateStatus.isError ? (
            <p className="text-sm text-destructive">
              {(createProduct.error as { detail?: string })?.detail ??
                (updateStatus.error as { detail?: string })?.detail ??
                "Could not create the product."}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              Create product
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
