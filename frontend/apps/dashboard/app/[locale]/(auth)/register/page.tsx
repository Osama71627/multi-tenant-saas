import { RegisterForm } from "@/components/register-form";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function RegisterPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations("auth");

  return (
    <div className="space-y-4">
      <RegisterForm locale={locale} />
      <p className="text-center text-sm text-muted-foreground">
        {t("haveAccount")}{" "}
        <Link href={`/${locale}/login`} className="font-medium text-primary underline">
          {t("signIn")}
        </Link>
      </p>
    </div>
  );
}
