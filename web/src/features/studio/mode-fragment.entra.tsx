"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-context";
import type { StudioLocale } from "@/features/studio/copy";

type EntraModeCopy = {
  sessionModeLabel: string;
  unauthenticatedDescription: string;
  signIn: string;
};

const entraModeCopy: Record<StudioLocale, EntraModeCopy> = {
  fr: {
    sessionModeLabel: "Redirection MSAL + PKCE",
    unauthenticatedDescription:
      "La connexion Entra utilise MSAL Browser avec redirection et PKCE.",
    signIn: "Se connecter avec Entra",
  },
  en: {
    sessionModeLabel: "MSAL redirect + PKCE",
    unauthenticatedDescription:
      "Entra sign-in uses MSAL Browser with redirect and PKCE.",
    signIn: "Sign in with Entra",
  },
};

export function sessionModeLabelFor(language: StudioLocale) {
  return entraModeCopy[language].sessionModeLabel;
}

export function Banner() {
  return null;
}

export function UnauthenticatedContent({
  language,
  cardTitle,
  error,
}: {
  language: StudioLocale;
  cardTitle: string;
  error: string | null;
}) {
  const auth = useAuth();
  const copy = entraModeCopy[language];

  return (
    <Card>
      <CardHeader title={cardTitle} description={copy.unauthenticatedDescription} />
      <Button onClick={() => void auth.signIn()}>{copy.signIn}</Button>
      {error ? <p className="mt-4 text-sm text-[var(--studio-danger)]">{error}</p> : null}
    </Card>
  );
}
