"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@saas/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@saas/ui/card";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { Skeleton } from "@saas/ui/skeleton";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useStore, useUpdateStore } from "@/lib/hooks/use-store";

const schema = z.object({
  name: z.string().min(1, "Required"),
  slug: z
    .string()
    .min(1, "Required")
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers, and hyphens only"),
  default_currency: z
    .string()
    .length(3, "3-letter code")
    .transform((v) => v.toUpperCase()),
  contact_email: z.union([z.literal(""), z.string().email("Invalid email")]),
  contact_phone: z.string(),
});
type FormValues = z.infer<typeof schema>;

export default function StoreSettingsPage() {
  const params = useParams<{ storeId: string }>();
  const { data: store, isLoading } = useStore(params.storeId);
  const updateStore = useUpdateStore(params.storeId);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: store
      ? {
          name: store.name,
          slug: store.slug,
          default_currency: store.default_currency ?? "",
          contact_email: store.contact_email ?? "",
          contact_phone: store.contact_phone ?? "",
        }
      : undefined,
  });

  useEffect(() => {
    if (!savedAt) return;
    const timeout = setTimeout(() => setSavedAt(null), 3000);
    return () => clearTimeout(timeout);
  }, [savedAt]);

  async function onSubmit(values: FormValues) {
    try {
      await updateStore.mutateAsync(values);
      setSavedAt(Date.now());
    } catch {
      // surfaced below via updateStore.error
    }
  }

  if (isLoading || !store) {
    return (
      <div className="max-w-xl space-y-6">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Store details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Store name</Label>
              <Input id="name" {...register("name")} />
              {errors.name ? (
                <p className="text-xs text-destructive">{errors.name.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="slug">Internal store slug</Label>
              <Input id="slug" {...register("slug")} />
              <p className="text-xs text-muted-foreground">
                An internal identifier for your store, not your public storefront address.
                Changing it does not move or update your live store URL.
              </p>
              {errors.slug ? (
                <p className="text-xs text-destructive">{errors.slug.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="default_currency">Default currency</Label>
              <Input id="default_currency" placeholder="SAR" {...register("default_currency")} />
              {errors.default_currency ? (
                <p className="text-xs text-destructive">{errors.default_currency.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="contact_email">Contact email</Label>
              <Input id="contact_email" type="email" {...register("contact_email")} />
              {errors.contact_email ? (
                <p className="text-xs text-destructive">{errors.contact_email.message}</p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="contact_phone">Contact phone</Label>
              <Input id="contact_phone" {...register("contact_phone")} />
            </div>

            {updateStore.isError ? (
              <p className="text-sm text-destructive">
                {(updateStore.error as { detail?: string })?.detail ??
                  "Could not save your changes."}
              </p>
            ) : null}
            {savedAt ? <p className="text-sm text-emerald-600">Saved.</p> : null}

            <Button type="submit" disabled={isSubmitting || !isDirty}>
              Save changes
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
