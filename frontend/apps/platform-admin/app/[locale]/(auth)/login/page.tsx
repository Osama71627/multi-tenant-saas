import { LoginForm } from "@/components/login-form";
import { getTranslations } from "next-intl/server";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations("platformAdmin");

  return (
    <div className="space-y-4">
      <p className="text-center text-sm font-medium text-muted-foreground">{t("brand")}</p>
      <LoginForm locale={locale} />
    </div>
  );
}
