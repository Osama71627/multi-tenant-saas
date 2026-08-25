"use client";

import { Select } from "@saas/ui/select";

import { useUpdateProductStatus } from "@/lib/hooks/use-products";

const STATUSES = ["draft", "active", "archived"] as const;

export function ProductStatusSelect({
  storeId,
  productId,
  status,
}: {
  storeId: string;
  productId: string;
  status: string;
}) {
  const updateStatus = useUpdateProductStatus(storeId);

  return (
    <div className="flex items-center gap-2">
      <Select
        className="h-7 w-28 py-0 text-xs"
        value={status}
        disabled={updateStatus.isPending}
        onChange={(e) => {
          updateStatus.mutate({
            productId,
            status: e.target.value as (typeof STATUSES)[number],
          });
        }}
      >
        {STATUSES.map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </Select>
      {updateStatus.isError ? (
        <span className="text-xs text-destructive">
          {(updateStatus.error as { detail?: string })?.detail ?? "Failed"}
        </span>
      ) : null}
    </div>
  );
}
