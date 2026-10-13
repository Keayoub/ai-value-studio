import { cn } from "@/lib/cn";

export function DataTable({
  caption,
  headers,
  rows,
  empty,
}: {
  caption: string;
  headers: string[];
  rows: Array<Array<React.ReactNode>>;
  empty: React.ReactNode;
}) {
  if (!rows.length) {
    return <>{empty}</>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--studio-border)]">
      <table className="min-w-full border-collapse text-sm" style={{ textAlign: "start" }}>
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-[var(--studio-surface-subtle)] text-[var(--studio-muted)]">
          <tr>
            {headers.map((header) => (
              <th key={header} className="px-4 py-3 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className={cn(rowIndex < rows.length - 1 && "border-b border-[var(--studio-border)]")}>
              {row.map((cell, cellIndex) => (
                <td key={`${rowIndex}-${cellIndex}`} className="px-4 py-3 align-top text-[var(--studio-foreground)]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
