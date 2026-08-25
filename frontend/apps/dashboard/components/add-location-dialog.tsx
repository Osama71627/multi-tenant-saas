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

import { useCreateStockLocation } from "@/lib/hooks/use-inventory";

const schema = z.object({ name: z.string().min(1, "Required") });
type FormValues = z.infer<typeof schema>;

export function AddLocationDialog({
  storeId,
  trigger,
}: {
  storeId: string;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const createLocation = useCreateStockLocation(storeId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { name: "" } });

  async function onSubmit(values: FormValues) {
    try {
      await createLocation.mutateAsync({ name: values.name });
      reset();
      setOpen(false);
    } catch {
      // surfaced below via createLocation.error
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
            <DialogTitle>Add stock location</DialogTitle>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="name">Location name</Label>
            <Input id="name" placeholder="Main warehouse" {...register("name")} />
            {errors.name ? <p className="text-xs text-destructive">{errors.name.message}</p> : null}
          </div>

          {createLocation.isError ? (
            <p className="text-sm text-destructive">
              {(createLocation.error as { detail?: string })?.detail ??
                "Could not create the location."}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              Add location
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
