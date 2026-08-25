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

import { useCreateProduct } from "@/lib/hooks/use-products";

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
      await createProduct.mutateAsync({
        name: values.name,
        slug: values.slug,
        sku: values.sku,
        price_amount: values.price_amount,
        description: "",
        seo_title: "",
        seo_description: "",
      });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via createProduct.error
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

          {createProduct.isError ? (
            <p className="text-sm text-destructive">
              {(createProduct.error as { detail?: string })?.detail ??
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
