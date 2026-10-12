import type { WorkspaceRole } from "@/features/api/types";
import type { StudioLocale } from "@/features/studio/copy";

export type DevIdentity = {
  subjectId: string;
  displayName: string;
  role: WorkspaceRole;
};

type StudioDevCopy = {
  sessionModeLabel: string;
  authBanner: string;
  unauthenticatedDescription: string;
  auth: {
    devSubject: string;
    displayName: string;
    role: string;
    selectIdentity: string;
  };
  toasts: {
    identitySelected: string;
  };
  defaults: {
    subjectId: string;
    displayName: string;
    role: WorkspaceRole;
  };
};

const studioDevCopy: Record<StudioLocale, StudioDevCopy> = {
  fr: {
    sessionModeLabel: "En-têtes de développement",
    authBanner: "LOCAL DEVELOPMENT — AUTH DISABLED",
    unauthenticatedDescription:
      "Sélectionnez une identité locale pour tester le vrai parcours applicatif connecté au backend.",
    auth: {
      devSubject: "Identifiant local",
      displayName: "Nom affiché",
      role: "Rôle",
      selectIdentity: "Sélectionner l’identité",
    },
    toasts: {
      identitySelected: "Identité locale sélectionnée",
    },
    defaults: {
      subjectId: "consultant",
      displayName: "Consultant local",
      role: "Consultant",
    },
  },
  en: {
    sessionModeLabel: "Development headers",
    authBanner: "LOCAL DEVELOPMENT — AUTH DISABLED",
    unauthenticatedDescription:
      "Choose a local identity to exercise the real application flow against the backend.",
    auth: {
      devSubject: "Local identifier",
      displayName: "Display name",
      role: "Role",
      selectIdentity: "Select identity",
    },
    toasts: {
      identitySelected: "Local identity selected",
    },
    defaults: {
      subjectId: "consultant",
      displayName: "Local Consultant",
      role: "Consultant",
    },
  },
};

export function studioDevCopyFor(locale: StudioLocale): StudioDevCopy {
  return studioDevCopy[locale];
}

export function defaultDevIdentityFor(locale: StudioLocale): DevIdentity {
  const defaults = studioDevCopyFor(locale).defaults;
  return {
    subjectId: defaults.subjectId,
    displayName: defaults.displayName,
    role: defaults.role,
  };
}
