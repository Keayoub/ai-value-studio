export function LabeledField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-2 text-sm font-medium text-[var(--studio-foreground)]">
      <span>{label}</span>
      {children}
    </label>
  );
}
