"use client";

import { Badge } from "@saas/ui/badge";
import { Button } from "@saas/ui/button";
import { Card, CardHeader, CardTitle } from "@saas/ui/card";
import { Input } from "@saas/ui/input";
import { Label } from "@saas/ui/label";
import { cn } from "@saas/ui/lib/cn";
import { Skeleton } from "@saas/ui/skeleton";
import { CheckCircle2, Loader2, Palette } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCreateStore } from "@/lib/hooks/use-create-store";
import { useThemePresets } from "@/lib/hooks/use-theme-presets";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
}

export function OnboardingWizard({ locale }: { locale: string }) {
  const t = useTranslations("onboarding");
  const router = useRouter();
  const { data: presets, isLoading: presetsLoading } = useThemePresets();
  const createStore = useCreateStore();

  const [step, setStep] = useState<"choose" | "details">("choose");
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleNameChange(value: string) {
    setName(value);
    if (!slugEdited) setSlug(slugify(value));
  }

  async function handleCreateStore() {
    setError(null);
    try {
      const store = await createStore.mutateAsync({
        name,
        slug,
        theme_preset_id: selectedPresetId ?? undefined,
      });
      router.push(`/${locale}/stores/${store.id}`);
    } catch {
      setError(t("createStoreError"));
    }
  }

  if (step === "choose") {
    return (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-12">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">{t("chooseTitle")}</h1>
          <p className="mt-1 text-muted-foreground">{t("chooseSubtitle")}</p>
        </div>

        {presetsLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {presets?.map((preset) => (
              <Card
                key={preset.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedPresetId(preset.id)}
                className={cn(
                  "cursor-pointer overflow-hidden transition-shadow hover:shadow-md",
                  selectedPresetId === preset.id && "ring-2 ring-primary"
                )}
              >
                <div className="flex h-28 items-center justify-center bg-muted">
                  {preset.preview_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- external/CMS-controlled preset images, next/image optimization not needed for an MVP static preview
                    <img
                      src={preset.preview_image_url}
                      alt={preset.name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <Palette className="h-8 w-8 text-muted-foreground" />
                  )}
                </div>
                <CardHeader className="p-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">{preset.name}</CardTitle>
                    {selectedPresetId === preset.id ? (
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    ) : null}
                  </div>
                  {preset.is_default ? (
                    <Badge variant="secondary" className="w-fit">
                      Recommended
                    </Badge>
                  ) : null}
                </CardHeader>
              </Card>
            ))}
          </div>
        )}

        <div className="flex justify-center">
          <Button onClick={() => setStep("details")} disabled={!selectedPresetId}>
            {t("continue")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 px-4 py-16">
      <h1 className="text-center text-2xl font-semibold">{t("detailsTitle")}</h1>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="store-name">{t("storeName")}</Label>
          <Input id="store-name" value={name} onChange={(e) => handleNameChange(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="store-slug">{t("storeSlug")}</Label>
          <Input
            id="store-slug"
            value={slug}
            onChange={(e) => {
              setSlugEdited(true);
              setSlug(slugify(e.target.value));
            }}
          />
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button
          className="w-full"
          disabled={!name || !slug || createStore.isPending}
          onClick={handleCreateStore}
        >
          {createStore.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("creating")}
            </>
          ) : (
            t("createStore")
          )}
        </Button>
      </div>
    </div>
  );
}
