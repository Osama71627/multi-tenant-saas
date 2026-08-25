import { LoginForm } from "@/components/login-form";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations("auth");

  return (
    <div className="space-y-4">
      <LoginForm locale={locale} />
      <p className="text-center text-sm text-muted-foreground">
        {t("noAccount")}{" "}
        <Link href={`/${locale}/register`} className="font-medium text-primary underline">
          {t("signUp")}
        </Link>
      </p>
    </div>
  );
}
