"use client";

import type { MutableRefObject } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";
import { localizeSeededDevFixtureName } from "@/features/studio/copy.dev";
import type {
  AssessmentEnvelope,
  DerivedAssessmentState,
  JsonValue,
  WizardQuestion,
  WizardStep,
} from "@/features/api/types";
import { cn } from "@/lib/cn";
import type { Locale, WizardCopy } from "@/features/studio/wizard/copy";
import {
  formatCurrency,
  splitListEntries,
  summarizeValue,
} from "@/features/studio/wizard/utils";

const runtimeConfig = getPublicRuntimeConfig(process.env);

function presentSeededFixtureValue(locale: Locale, value: string | null | undefined) {
  return runtimeConfig.authMode === "dev" ? localizeSeededDevFixtureName(locale, value) : value;
}

export function StepForm({
  step,
  labels,
  fieldRefs,
  fieldErrors,
  onQuestionChange,
}: {
  step: WizardStep;
  labels: WizardCopy;
  fieldRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  fieldErrors: Record<string, string>;
  onQuestionChange: (
    question: WizardQuestion,
    rawValue: string | boolean | number | string[],
  ) => void;
}) {
  const visibleQuestions = step.questions.filter((question) => question.visible);
  return (
    <div className="space-y-5">
      {visibleQuestions.map((question) => (
        <QuestionField
          key={question.key}
          labels={labels}
          question={question}
          error={fieldErrors[question.key] ?? null}
          refCallback={(element) => {
            fieldRefs.current[question.key] = element;
          }}
          onChange={onQuestionChange}
        />
      ))}
    </div>
  );
}

export function ReviewPanel({
  envelope,
  locale,
  labels,
  onEditQuestion,
  fieldRefs,
  onQuestionChange,
  fieldErrors,
}: {
  envelope: AssessmentEnvelope;
  locale: Locale;
  labels: WizardCopy;
  onEditQuestion: (step: number, questionKey: string) => void;
  fieldRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  onQuestionChange: (
    question: WizardQuestion,
    rawValue: string | boolean | number | string[],
  ) => void;
  fieldErrors: Record<string, string>;
}) {
  const reviewStep = envelope.template.steps.find((step) => step.index === 8);
  const factRows = envelope.template.steps
    .filter((step) => step.index >= 1 && step.index < 8)
    .flatMap((step) =>
      step.questions
        .filter((question) => question.visible)
        .map((question) => ({ step, question })),
    );
  return (
    <div className="space-y-6">
      <Card className="shadow-[var(--shadow-sm)]">
        <CardHeader title={labels.review} description={labels.reviewDescription} />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr),minmax(0,0.7fr)]">
          <section className="rounded-2xl border border-[var(--studio-border)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-[var(--studio-foreground)]">
                  {labels.facts}
                </h3>
                <p className="text-sm text-[var(--studio-muted)]">{labels.reviewDescription}</p>
              </div>
            </div>
            <ul className="mt-4 space-y-3">
              {factRows.map(({ step, question }) => (
                <li
                  key={question.key}
                  className="rounded-xl border border-[var(--studio-border)] bg-[var(--studio-surface)] p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-[var(--studio-foreground)]">
                        {question.label}
                      </p>
                      <p className="text-sm text-[var(--studio-muted)]">
                        {summarizeValue(question.value, locale, labels)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      className="px-3"
                      onClick={() => onEditQuestion(step.index, question.key)}
                    >
                      {labels.editAnswer}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <div className="space-y-4">
            <Card className="shadow-none">
              <CardHeader title={labels.recommendationSummary} />
              <dl className="space-y-3 text-sm">
                <SummaryRow
                  label={labels.sponsor}
                  value={presentSeededFixtureValue(locale, envelope.derived.sponsor_name) ?? labels.noData}
                />
                <SummaryRow
                  label={labels.riskProfile}
                  value={envelope.derived.risk_profile ?? labels.noData}
                />
                {envelope.derived.step4_preview ? (
                  <>
                    <SummaryRow
                      label={labels.derivedValue}
                      value={formatCurrency(envelope.derived.step4_preview.net_value, locale)}
                    />
                    <SummaryRow
                      label={labels.grossValue}
                      value={formatCurrency(envelope.derived.step4_preview.gross_value, locale)}
                    />
                  </>
                ) : (
                  <SummaryRow label={labels.derivedValue} value={labels.noValuePreview} />
                )}
              </dl>
            </Card>
            <Card className="shadow-none">
              <CardHeader title={labels.missingInformation} />
              {envelope.derived.missing_information.length > 0 ? (
                <ul className="list-disc space-y-2 ps-5 text-sm text-[var(--studio-muted)]">
                  {envelope.derived.missing_information.map((entry, index) => (
                    <li key={`${index}:${entry}`}>{entry}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[var(--studio-muted)]">{labels.noData}</p>
              )}
            </Card>
          </div>
        </div>
      </Card>
      {reviewStep ? (
        <StepForm
          step={reviewStep}
          labels={labels}
          fieldRefs={fieldRefs}
          fieldErrors={fieldErrors}
          onQuestionChange={onQuestionChange}
        />
      ) : null}
    </div>
  );
}

export function DerivedPanel({
  derived,
  locale,
  labels,
}: {
  derived: DerivedAssessmentState;
  locale: Locale;
  labels: WizardCopy;
}) {
  return (
    <Card className="shadow-[var(--shadow-sm)]">
      <CardHeader title={labels.recommendationSummary} />
      <dl className="space-y-3 text-sm">
        <SummaryRow
          label={labels.sponsor}
          value={presentSeededFixtureValue(locale, derived.sponsor_name) ?? labels.noData}
        />
        <SummaryRow label={labels.riskProfile} value={derived.risk_profile ?? labels.noData} />
        {derived.step4_preview ? (
          <>
            <SummaryRow
              label={labels.derivedValue}
              value={formatCurrency(derived.step4_preview.net_value, locale)}
            />
            <SummaryRow
              label={labels.grossValue}
              value={formatCurrency(derived.step4_preview.gross_value, locale)}
            />
          </>
        ) : (
          <SummaryRow label={labels.derivedValue} value={labels.noValuePreview} />
        )}
      </dl>
      <div className="mt-4 rounded-2xl bg-[var(--studio-surface-subtle)] p-4">
        <h3 className="font-semibold text-[var(--studio-foreground)]">
          {labels.missingInformation}
        </h3>
        {derived.missing_information.length > 0 ? (
          <ul className="mt-2 list-disc space-y-2 ps-5 text-sm text-[var(--studio-muted)]">
            {derived.missing_information.map((entry, index) => (
              <li key={`${index}:${entry}`}>{entry}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[var(--studio-muted)]">{labels.noData}</p>
        )}
      </div>
    </Card>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm font-semibold text-[var(--studio-muted)]">{label}</dt>
      <dd className="mt-1 text-[var(--studio-foreground)]">{value}</dd>
    </div>
  );
}

function QuestionField({
  question,
  labels,
  error,
  refCallback,
  onChange,
}: {
  question: WizardQuestion;
  labels: WizardCopy;
  error: string | null;
  refCallback: (element: HTMLElement | null) => void;
  onChange: (
    question: WizardQuestion,
    rawValue: string | boolean | number | string[],
  ) => void;
}) {
  const fieldId = `wizard-${question.key}`;
  const descriptionId = `${fieldId}-description`;
  const errorId = `${fieldId}-error`;
  const commonProps = {
    id: fieldId,
    "aria-describedby": [question.help_text ? descriptionId : null, error ? errorId : null]
      .filter(Boolean)
      .join(" "),
    "aria-invalid": error ? true : undefined,
    disabled: question.read_only,
  };

  return (
    <div className="space-y-2">
      <label
        htmlFor={fieldId}
        className="block text-sm font-medium text-[var(--studio-foreground)]"
      >
        {question.label}
        {question.required ? (
          <>
            {" "}
            <span aria-hidden="true">*</span>
            <span className="sr-only">{labels.questionRequired}</span>
          </>
        ) : null}
      </label>
      {question.help_text ? (
        <p id={descriptionId} className="text-sm text-[var(--studio-muted)]">
          {question.help_text}
        </p>
      ) : null}
      {renderField(question, labels, commonProps, refCallback, onChange)}
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-[var(--studio-danger)]">
          {error}
        </p>
      ) : null}
      {question.source === "ai_assisted" ? <Badge tone="info">{labels.aiAssisted}</Badge> : null}
    </div>
  );
}

function renderField(
  question: WizardQuestion,
  labels: WizardCopy,
  commonProps: {
    id: string;
    "aria-describedby": string;
    "aria-invalid": boolean | undefined;
    disabled: boolean;
  },
  refCallback: (element: HTMLElement | null) => void,
  onChange: (
    question: WizardQuestion,
    rawValue: string | boolean | number | string[],
  ) => void,
) {
  if (question.field_type === "textarea") {
    return (
      <Textarea
        {...commonProps}
        ref={(element) => refCallback(element)}
        value={typeof question.value === "string" ? question.value : ""}
        placeholder={question.placeholder ?? undefined}
        onChange={(event) => onChange(question, event.target.value)}
      />
    );
  }

  if (question.field_type === "list") {
    const value = Array.isArray(question.value)
      ? question.value.join("\n")
      : typeof question.value === "string"
        ? question.value
        : "";
    return (
      <Textarea
        {...commonProps}
        ref={(element) => refCallback(element)}
        value={value}
        placeholder={question.placeholder ?? undefined}
        onChange={(event) => onChange(question, event.target.value)}
      />
    );
  }

  if (question.field_type === "select") {
    return (
      <Select
        {...commonProps}
        ref={(element) => refCallback(element)}
        value={typeof question.value === "string" ? question.value : ""}
        onChange={(event) => onChange(question, event.target.value)}
      >
        <option value="">{labels.chooseOption}</option>
        {question.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    );
  }

  if (question.field_type === "radio") {
    return (
      <fieldset ref={(element) => refCallback(element)} className="space-y-3">
        <legend className="sr-only">{question.label}</legend>
        {question.options.map((option) => (
          <label
            key={option.value}
            className="flex items-center gap-3 rounded-xl border border-[var(--studio-border)] px-3 py-3"
          >
            <input
              type="radio"
              name={commonProps.id}
              value={option.value}
              aria-label={`${question.label} — ${option.label}`}
              checked={question.value === option.value}
              disabled={question.read_only}
              onChange={(event) => onChange(question, event.target.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (question.field_type === "boolean") {
    return (
      <fieldset ref={(element) => refCallback(element)} className="space-y-3">
        <legend className="sr-only">{question.label}</legend>
        <label className="flex items-center gap-3 rounded-xl border border-[var(--studio-border)] px-3 py-3">
          <input
            type="radio"
            name={commonProps.id}
            aria-label={`${question.label} — ${labels.yes}`}
            checked={question.value === true}
            disabled={question.read_only}
            onChange={() => onChange(question, true)}
          />
          <span>{labels.yes}</span>
        </label>
        <label className="flex items-center gap-3 rounded-xl border border-[var(--studio-border)] px-3 py-3">
          <input
            type="radio"
            name={commonProps.id}
            aria-label={`${question.label} — ${labels.no}`}
            checked={question.value === false}
            disabled={question.read_only}
            onChange={() => onChange(question, false)}
          />
          <span>{labels.no}</span>
        </label>
      </fieldset>
    );
  }

  if (question.field_type === "multiselect") {
    const selected = Array.isArray(question.value)
      ? question.value.filter((entry): entry is string => typeof entry === "string")
      : [];
    return (
      <fieldset ref={(element) => refCallback(element)} className="space-y-3">
        <legend className="sr-only">{question.label}</legend>
        {question.options.map((option) => {
          const checked = selected.includes(option.value);
          return (
            <label
              key={option.value}
              className="flex items-center gap-3 rounded-xl border border-[var(--studio-border)] px-3 py-3"
            >
              <input
                type="checkbox"
                name={`${commonProps.id}-${option.value}`}
                aria-label={`${question.label} — ${option.label}`}
                checked={checked}
                disabled={question.read_only}
                onChange={(event) => {
                  const nextSelected = event.target.checked
                    ? [...selected, option.value]
                    : selected.filter((entry) => entry !== option.value);
                  onChange(question, nextSelected);
                }}
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </fieldset>
    );
  }

  if (question.field_type === "scale_1_to_5") {
    return (
      <fieldset ref={(element) => refCallback(element)} className="grid grid-cols-5 gap-2">
        <legend className="sr-only">{question.label}</legend>
        {[1, 2, 3, 4, 5].map((value) => (
          <label
            key={value}
            className={cn(
              "flex min-h-10 items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm",
              question.value === value
                ? "border-[var(--studio-brand)] bg-[var(--studio-surface-subtle)] text-[var(--studio-foreground)]"
                : "border-[var(--studio-border)] text-[var(--studio-muted)]",
            )}
          >
            <input
              type="radio"
              name={commonProps.id}
              aria-label={`${question.label} — ${value}`}
              checked={question.value === value}
              disabled={question.read_only}
              onChange={() => onChange(question, value)}
            />
            <span>{value}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (question.field_type === "money") {
    return (
      <div className="relative">
        <Input
          {...commonProps}
          ref={(element) => refCallback(element)}
          type="number"
          inputMode="decimal"
          value={
            typeof question.value === "string" || typeof question.value === "number"
              ? String(question.value)
              : ""
          }
          placeholder={question.placeholder ?? undefined}
          onChange={(event) => onChange(question, event.target.value)}
          className="pe-16"
        />
        <span className="pointer-events-none absolute inset-y-0 end-3 flex items-center text-sm text-[var(--studio-muted)]">
          {labels.currencySuffix}
        </span>
      </div>
    );
  }

  return (
    <Input
      {...commonProps}
      ref={(element) => refCallback(element)}
      type={question.field_type === "number" || question.field_type === "integer" ? "number" : "text"}
      inputMode={question.field_type === "number" || question.field_type === "integer" ? "decimal" : undefined}
      value={formatInputValue(question.value)}
      placeholder={question.placeholder ?? undefined}
      onChange={(event) => onChange(question, event.target.value)}
    />
  );
}

function formatInputValue(value: JsonValue | null): string {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return splitListEntries(value.join("\n")).join("\n");
  }
  return "";
}
