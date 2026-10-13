import { cn } from "@/lib/cn";

export function DataTable({
  caption,
  headers,
  rows,
  empty,
  rowHeaderIndex = 0,
}: {
  caption: string;
  headers: string[];
  rows: Array<Array<React.ReactNode>>;
  empty: React.ReactNode;
  rowHeaderIndex?: number;
}) {
  if (!rows.length) {
    return <>{empty}</>;
  }
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--studio-border)] bg-[var(--studio-surface)]">
      <table className="min-w-full border-collapse text-sm" style={{ textAlign: "start" }}>
        <caption className="sr-only">{caption}</caption>
        <thead className="hidden bg-[var(--studio-surface-subtle)] text-[var(--studio-muted)] sm:table-header-group">
          <tr>
            {headers.map((header) => (
              <th key={header} scope="col" className="px-4 py-3 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--studio-border)] sm:divide-y-0">
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={cn(
                "block p-4 sm:table-row sm:p-0",
                rowIndex < rows.length - 1 && "sm:border-b sm:border-[var(--studio-border)]",
              )}
            >
              {row.map((cell, cellIndex) => (
                cellIndex === rowHeaderIndex ? (
                  <th
                    key={`${rowIndex}-${cellIndex}`}
                    scope="row"
                    data-label={headers[cellIndex]}
                    className="flex items-start justify-between gap-4 py-2 text-left align-top text-[var(--studio-foreground)] before:pe-4 before:text-xs before:font-semibold before:uppercase before:tracking-[0.08em] before:text-[var(--studio-muted)] before:content-[attr(data-label)] sm:table-cell sm:px-4 sm:py-3 sm:before:content-none"
                  >
                    <span className="font-semibold">{cell}</span>
                  </th>
                ) : (
                  <td
                    key={`${rowIndex}-${cellIndex}`}
                    data-label={headers[cellIndex]}
                    className="flex items-start justify-between gap-4 py-2 align-top text-[var(--studio-foreground)] before:pe-4 before:text-xs before:font-semibold before:uppercase before:tracking-[0.08em] before:text-[var(--studio-muted)] before:content-[attr(data-label)] sm:table-cell sm:px-4 sm:py-3 sm:before:content-none"
                  >
                    <span className="text-right sm:text-left">{cell}</span>
                  </td>
                )
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
