"use client";

import { useState } from "react";

import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/features/auth/auth-context";
import { formatWorkspaceRoleLabel, type StudioLocale } from "@/features/studio/copy";
import {
  defaultDevIdentityFor,
  studioDevCopyFor,
  type DevIdentity,
} from "@/features/studio/copy.dev";
import { LabeledField } from "@/features/studio/shared";

export function sessionModeLabelFor(language: StudioLocale) {
  return studioDevCopyFor(language).sessionModeLabel;
}

export function Banner({ language }: { language: StudioLocale }) {
  const copy = studioDevCopyFor(language);
  const auth = useAuth();
  const roleLabel =
    auth.roleLabel && ["Consultant", "Sponsor", "Contributor", "WorkspaceAdmin"].includes(auth.roleLabel)
      ? formatWorkspaceRoleLabel(language, auth.roleLabel as DevIdentity["role"])
      : auth.roleLabel;
  return (
    <div className="bg-[var(--studio-banner)] px-4 py-3 text-center text-sm font-semibold text-white">
      {copy.authBanner}
      {auth.displayName || roleLabel ? (
        <span>
          {" "}
          · {auth.displayName ?? "—"} · {roleLabel ?? "—"}
        </span>
      ) : null}
    </div>
  );
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
  const toast = useToast();
  const copy = studioDevCopyFor(language);
  const [devIdentity, setDevIdentity] = useState<DevIdentity>(() => defaultDevIdentityFor(language));

  async function handleSelectIdentity() {
    await auth.selectDevIdentity(devIdentity);
    toast.push({
      tone: "success",
      title: copy.toasts.identitySelected,
      detail: formatWorkspaceRoleLabel(language, devIdentity.role),
    });
  }

  return (
    <Card>
      <CardHeader title={cardTitle} description={copy.unauthenticatedDescription} />
      <div className="grid gap-4 md:grid-cols-2">
        <LabeledField label={copy.auth.devSubject}>
          <Input
            value={devIdentity.subjectId}
            onChange={(event) =>
              setDevIdentity((current) => ({ ...current, subjectId: event.target.value }))
            }
          />
        </LabeledField>
        <LabeledField label={copy.auth.displayName}>
          <Input
            value={devIdentity.displayName}
            onChange={(event) =>
              setDevIdentity((current) => ({ ...current, displayName: event.target.value }))
            }
          />
        </LabeledField>
        <LabeledField label={copy.auth.role}>
          <Select
            value={devIdentity.role}
            onChange={(event) =>
              setDevIdentity((current) => ({
                ...current,
                role: event.target.value as DevIdentity["role"],
              }))
            }
          >
            <option value="Consultant">{formatWorkspaceRoleLabel(language, "Consultant")}</option>
            <option value="WorkspaceAdmin">
              {formatWorkspaceRoleLabel(language, "WorkspaceAdmin")}
            </option>
            <option value="Sponsor">{formatWorkspaceRoleLabel(language, "Sponsor")}</option>
            <option value="Contributor">{formatWorkspaceRoleLabel(language, "Contributor")}</option>
          </Select>
        </LabeledField>
        <div className="flex items-end">
          <Button className="w-full" onClick={() => void handleSelectIdentity()}>
            {copy.auth.selectIdentity}
          </Button>
        </div>
      </div>
      {error ? <p className="mt-4 text-sm text-[var(--studio-danger)]">{error}</p> : null}
    </Card>
  );
}
