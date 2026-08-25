"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@saas/ui/dialog";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { Select } from "@saas/ui/select";
import { Separator } from "@saas/ui/separator";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api } from "@/lib/api-client";
import { useCreateShippingMethod, useShippingMethods } from "@/lib/hooks/use-shipping-zones";

const KINDS = [
  { value: "flat", label: "Flat rate" },
  { value: "free", label: "Free shipping" },
  { value: "weight_based", label: "Weight based" },
  { value: "price_based", label: "Order value based" },
  { value: "carrier_calculated", label: "Carrier calculated" },
] as const;

const schema = z.object({
  name: z.string().min(1, "Required"),
  kind: z.enum(["flat", "free", "weight_based", "price_based", "carrier_calculated"]),
  price_amount: z.coerce.number().int().min(0),
  currency: z.string().length(3, "3-letter code"),
});
type FormValues = z.infer<typeof schema>;

export function ManageShippingMethodsDialog({
  storeId,
  zoneId,
  zoneName,
  trigger,
}: {
  storeId: string;
  zoneId: string;
  zoneName: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const { data: methods, isLoading } = useShippingMethods(storeId, zoneId, open);
  const createMethod = useCreateShippingMethod(storeId, zoneId);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", kind: "flat", price_amount: 0, currency: "USD" },
  });
  const kind = watch("kind");
  const needsPrice = kind === "flat" || kind === "free";

  async function onSubmit(values: FormValues) {
    try {
      const method = await createMethod.mutateAsync({
        name: values.name,
        kind: values.kind,
      });
      if (needsPrice && method?.id) {
        await createRateFor(method.id, values);
      }
      reset();
    } catch {
      // surfaced below via createMethod.error / rateError
    }
  }

  const [rateError, setRateError] = useState<string | null>(null);

  async function createRateFor(methodId: string, values: FormValues) {
    setRateError(null);
    try {
      const { error } = await api.POST(
        "/api/v1/dashboard/stores/{store_id}/shipping/methods/{method_id}/rates",
        {
          params: { path: { store_id: storeId, method_id: methodId } },
          body: {
            method: methodId,
            price_amount: values.kind === "free" ? 0 : values.price_amount,
            currency: values.currency,
          },
        }
      );
      if (error) {
        setRateError(
          (error as { detail?: string })?.detail ?? "Method created, but the rate failed to save."
        );
      }
    } catch {
      setRateError("Method created, but the rate failed to save.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Shipping methods — {zoneName}</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !methods?.length ? (
          <p className="text-sm text-muted-foreground">
            No shipping methods in this zone yet. Add one below.
          </p>
        ) : (
          <ul className="space-y-2">
            {methods.map((method) => (
              <li
                key={method.id}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <span className="font-medium">{method.name}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{method.kind}</Badge>
                  <Badge variant={method.is_active ? "success" : "secondary"}>
                    {method.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        )}

        <Separator />

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <p className="text-sm font-medium">Add a shipping method</p>

          <div className="space-y-1.5">
            <Label htmlFor="method-name">Method name</Label>
            <Input id="method-name" placeholder="Standard shipping" {...register("name")} />
            {errors.name ? <p className="text-xs text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="method-kind">Kind</Label>
            <Select id="method-kind" {...register("kind")}>
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
            {kind === "weight_based" || kind === "price_based" || kind === "carrier_calculated" ? (
              <p className="text-xs text-muted-foreground">
                This method will be created without a rate — tiered/carrier rates aren&apos;t
                configurable here yet.
              </p>
            ) : null}
          </div>

          {needsPrice ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="price_amount">Price (minor units)</Label>
                <Input
                  id="price_amount"
                  type="number"
                  min={0}
                  disabled={kind === "free"}
                  {...register("price_amount")}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="currency">Currency</Label>
                <Input id="currency" placeholder="USD" {...register("currency")} />
                {errors.currency ? (
                  <p className="text-xs text-destructive">{errors.currency.message}</p>
                ) : null}
              </div>
            </div>
          ) : null}

          {createMethod.isError ? (
            <p className="text-sm text-destructive">
              {(createMethod.error as { detail?: string })?.detail ?? "Could not add the method."}
            </p>
          ) : null}
          {rateError ? <p className="text-sm text-destructive">{rateError}</p> : null}

          <Button type="submit" disabled={isSubmitting}>
            Add method
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
