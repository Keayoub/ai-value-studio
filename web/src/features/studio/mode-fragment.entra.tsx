"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-context";
import { isDesktopRuntime } from "@/features/auth/runtime";
import type { StudioLocale } from "@/features/studio/copy";

type EntraModeCopy = {
  sessionModeLabel: string;
  desktopSessionModeLabel: string;
  unauthenticatedDescription: string;
  desktopUnauthenticatedDescription: string;
  signIn: string;
};

const entraModeCopy: Record<StudioLocale, EntraModeCopy> = {
  fr: {
    sessionModeLabel: "Redirection MSAL + PKCE",
    desktopSessionModeLabel: "Navigateur système + boucle locale PKCE",
    unauthenticatedDescription:
      "La connexion Entra utilise MSAL Browser avec redirection et PKCE.",
    desktopUnauthenticatedDescription:
      "La connexion bureau ouvre le navigateur système, finalise PKCE dans le process principal, puis ne transmet au renderer qu’un jeton d’accès.",
    signIn: "Se connecter avec Entra",
  },
  en: {
    sessionModeLabel: "MSAL redirect + PKCE",
    desktopSessionModeLabel: "System browser + loopback PKCE",
    unauthenticatedDescription:
      "Entra sign-in uses MSAL Browser with redirect and PKCE.",
    desktopUnauthenticatedDescription:
      "Desktop sign-in opens the system browser, completes PKCE in the main process, and exposes only an access token to the renderer.",
    signIn: "Sign in with Entra",
  },
};

export function sessionModeLabelFor(language: StudioLocale) {
  return isDesktopRuntime()
    ? entraModeCopy[language].desktopSessionModeLabel
    : entraModeCopy[language].sessionModeLabel;
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
  const description = isDesktopRuntime()
    ? copy.desktopUnauthenticatedDescription
    : copy.unauthenticatedDescription;

  return (
    <Card>
      <CardHeader title={cardTitle} description={description} />
      <Button onClick={() => void auth.signIn()}>{copy.signIn}</Button>
      {error ? <p className="mt-4 text-sm text-[var(--studio-danger)]">{error}</p> : null}
    </Card>
  );
}
