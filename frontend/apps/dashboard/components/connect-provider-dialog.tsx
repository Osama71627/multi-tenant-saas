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

import { useConnectPaymentProvider } from "@/lib/hooks/use-payment-providers";

const PROVIDERS = [
  { value: "manual_cod", label: "Cash on delivery" },
  { value: "stripe", label: "Stripe" },
  { value: "mock", label: "Mock (testing)" },
] as const;

const schema = z.object({
  provider_key: z.enum(["manual_cod", "stripe", "mock"]),
  mode: z.enum(["test", "live"]),
  credentials: z.string(),
  webhook_secret: z.string(),
});
type FormValues = z.infer<typeof schema>;

export function ConnectProviderDialog({
  storeId,
  trigger,
}: {
  storeId: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const connectProvider = useConnectPaymentProvider(storeId);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { provider_key: "manual_cod", mode: "test", credentials: "", webhook_secret: "" },
  });
  const providerKey = watch("provider_key");

  async function onSubmit(values: FormValues) {
    try {
      await connectProvider.mutateAsync({
        provider_key: values.provider_key,
        mode: values.mode,
        credentials: values.credentials,
        webhook_secret: values.webhook_secret,
      });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via connectProvider.error
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
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" autoComplete="off">
          <DialogHeader>
            <DialogTitle>Connect payment provider</DialogTitle>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="provider_key">Provider</Label>
            <Select id="provider_key" {...register("provider_key")}>
              {PROVIDERS.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="mode">Mode</Label>
            <Select id="mode" {...register("mode")}>
              <option value="test">Test</option>
              <option value="live">Live</option>
            </Select>
          </div>

          {providerKey === "stripe" ? (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="credentials">Secret key</Label>
                <Input
                  id="credentials"
                  type="password"
                  autoComplete="off"
                  {...register("credentials")}
                />
                <p className="text-xs text-muted-foreground">
                  Stored encrypted. Never shown again after saving.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="webhook_secret">Webhook signing secret</Label>
                <Input
                  id="webhook_secret"
                  type="password"
                  autoComplete="off"
                  {...register("webhook_secret")}
                />
              </div>
            </>
          ) : null}

          {connectProvider.isError ? (
            <p className="text-sm text-destructive">
              {(connectProvider.error as { detail?: string })?.detail ??
                "Could not connect the provider."}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              Connect
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
