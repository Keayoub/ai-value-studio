import type {
  JsonValue,
  WizardQuestion,
} from "@/features/api/types";

import type { Locale, WizardCopy } from "@/features/studio/wizard/copy";

export function formatTime(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-FR" : "en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function summarizeValue(value: JsonValue, locale: Locale, labels: WizardCopy): string {
  if (value === null) {
    return labels.noData;
  }
  if (typeof value === "boolean") {
    return value ? labels.yes : labels.no;
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-US").format(value);
  }
  if (typeof value === "string") {
    return value.trim() || labels.noData;
  }
  if (Array.isArray(value)) {
    return value.map((entry) => summarizeValue(entry, locale, labels)).join(", ");
  }
  return Object.entries(value)
    .map(([key, entry]) => `${key}: ${summarizeValue(entry, locale, labels)}`)
    .join(", ");
}

export function formatCurrency(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-US", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function parseQuestionValue(
  question: WizardQuestion,
  rawValue: string | boolean | number | string[],
): JsonValue {
  if (typeof rawValue === "boolean" || typeof rawValue === "number" || Array.isArray(rawValue)) {
    return rawValue;
  }
  if (question.field_type === "scale_1_to_5") {
    return rawValue ? Number(rawValue) : rawValue;
  }
  return rawValue;
}

export function normalizeForServer(question: WizardQuestion, value: JsonValue): JsonValue | null {
  const schemaType = question.schema.type;
  if (schemaType === "integer") {
    if (typeof value === "number" && Number.isInteger(value)) {
      return value;
    }
    if (typeof value !== "string") {
      return null;
    }
    const trimmed = value.trim();
    if (!/^-?\d+$/.test(trimmed)) {
      return null;
    }
    return Number.parseInt(trimmed, 10);
  }
  if (schemaType === "number") {
    if (typeof value === "number") {
      return Number.isFinite(value) ? value : null;
    }
    if (typeof value !== "string") {
      return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number.parseFloat(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (schemaType === "boolean") {
    return typeof value === "boolean" ? value : null;
  }
  if (schemaType === "string") {
    return typeof value === "string" ? value : null;
  }
  if (schemaType === "array") {
    if (question.field_type === "list") {
      const entries = typeof value === "string" ? splitListEntries(value) : value;
      return Array.isArray(entries) ? sanitizeStringArray(entries) : null;
    }
    if (question.field_type === "multiselect") {
      return Array.isArray(value) ? sanitizeStringArray(value) : null;
    }
  }
  return value;
}

export function splitListEntries(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function sanitizeStringArray(value: JsonValue[]): string[] | null {
  const entries: string[] = [];
  for (const entry of value) {
    if (typeof entry !== "string") {
      return null;
    }
    const trimmed = entry.trim();
    if (trimmed) {
      entries.push(trimmed);
    }
  }
  return entries;
}
