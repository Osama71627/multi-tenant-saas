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

import { useCreateShippingZone } from "@/lib/hooks/use-shipping-zones";

const schema = z.object({
  name: z.string().min(1, "Required"),
  countries: z.string(),
  priority: z.coerce.number().int(),
});
type FormValues = z.infer<typeof schema>;

export function AddShippingZoneDialog({
  storeId,
  trigger,
}: {
  storeId: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const createZone = useCreateShippingZone(storeId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", countries: "", priority: 0 },
  });

  async function onSubmit(values: FormValues) {
    try {
      await createZone.mutateAsync({
        name: values.name,
        countries: values.countries
          .split(",")
          .map((code) => code.trim().toUpperCase())
          .filter(Boolean),
        priority: values.priority,
      });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via createZone.error
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
            <DialogTitle>Add shipping zone</DialogTitle>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="name">Zone name</Label>
            <Input id="name" {...register("name")} />
            {errors.name ? <p className="text-xs text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="countries">Countries</Label>
            <Input id="countries" placeholder="SA, AE, KW" {...register("countries")} />
            <p className="text-xs text-muted-foreground">
              Comma-separated ISO country codes. Leave blank to match any country.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="priority">Priority</Label>
            <Input id="priority" type="number" {...register("priority")} />
            <p className="text-xs text-muted-foreground">Lower numbers are matched first.</p>
            {errors.priority ? (
              <p className="text-xs text-destructive">{errors.priority.message}</p>
            ) : null}
          </div>

          {createZone.isError ? (
            <p className="text-sm text-destructive">
              {(createZone.error as { detail?: string })?.detail ??
                "Could not create the shipping zone."}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              Create zone
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
