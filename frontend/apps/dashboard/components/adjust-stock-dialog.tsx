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
import { Select } from "@saas/ui/select";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAdjustStock, useStockLocations } from "@/lib/hooks/use-inventory";
import { useProducts } from "@/lib/hooks/use-products";

const schema = z.object({
  variant: z.string().min(1, "Required"),
  location: z.string().min(1, "Required"),
  delta: z.coerce.number().int().refine((n) => n !== 0, "Must not be zero"),
  reason: z.string().min(1, "Required"),
});
type FormValues = z.infer<typeof schema>;

export function AdjustStockDialog({
  storeId,
  trigger,
}: {
  storeId: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const { data: products } = useProducts(storeId);
  const { data: locations } = useStockLocations(storeId);
  const adjustStock = useAdjustStock(storeId);

  const variantOptions = (products ?? []).flatMap((product) =>
    (product.variants ?? []).map((variant) => ({
      id: variant.id ?? "",
      label: `${product.name} — ${variant.sku}`,
    }))
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { variant: "", location: "", delta: 0, reason: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      await adjustStock.mutateAsync({
        variant: values.variant,
        location: values.location,
        delta: values.delta,
        reason: values.reason,
        reference: "",
      });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via adjustStock.error
    }
  }

  const noLocations = !locations?.length;
  const noVariants = variantOptions.length === 0;

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
        {noLocations || noVariants ? (
          <div className="space-y-2">
            <DialogHeader>
              <DialogTitle>Adjust stock</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              {noLocations
                ? "Add a stock location first, then come back here to adjust stock."
                : "Add a product first, then come back here to adjust stock."}
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <DialogHeader>
              <DialogTitle>Adjust stock</DialogTitle>
            </DialogHeader>

            <div className="space-y-1.5">
              <Label htmlFor="variant">Product</Label>
              <Select id="variant" {...register("variant")}>
                <option value="">Select a product…</option>
                {variantOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </Select>
              {errors.variant ? (
                <p className="text-xs text-destructive">{errors.variant.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="location">Location</Label>
              <Select id="location" {...register("location")}>
                <option value="">Select a location…</option>
                {(locations ?? []).map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </Select>
              {errors.location ? (
                <p className="text-xs text-destructive">{errors.location.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="delta">Quantity change</Label>
              <Input id="delta" type="number" placeholder="10 or -5" {...register("delta")} />
              <p className="text-xs text-muted-foreground">
                Positive to add stock, negative to remove it.
              </p>
              {errors.delta ? (
                <p className="text-xs text-destructive">{errors.delta.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="reason">Reason</Label>
              <Input id="reason" placeholder="Initial stock, recount, damage…" {...register("reason")} />
              {errors.reason ? (
                <p className="text-xs text-destructive">{errors.reason.message}</p>
              ) : null}
            </div>

            {adjustStock.isError ? (
              <p className="text-sm text-destructive">
                {(adjustStock.error as { detail?: string })?.detail ??
                  "Could not adjust stock."}
              </p>
            ) : null}

            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>
                Save adjustment
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
