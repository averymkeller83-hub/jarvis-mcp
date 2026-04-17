import { useState, useCallback, type ReactNode } from "react";

interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  keyField: string;
  emptyMessage?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  keyField,
  emptyMessage = "No data available",
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey],
  );

  const sorted = [...data].sort((a, b) => {
    if (!sortKey) return 0;
    const av = String(a[sortKey] ?? "");
    const bv = String(b[sortKey] ?? "");
    const cmp = av.localeCompare(bv);
    return sortDir === "asc" ? cmp : -cmp;
  });

  if (data.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-text-muted text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border-subtle">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-left section-title py-3 px-4 ${
                  col.sortable !== false
                    ? "cursor-pointer select-none hover:text-text-secondary transition-colors"
                    : ""
                }`}
                onClick={() =>
                  col.sortable !== false && handleSort(col.key)
                }
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                      {sortDir === "asc" ? (
                        <path d="M6 2l4 5H2l4-5z" />
                      ) : (
                        <path d="M6 10l4-5H2l4 5z" />
                      )}
                    </svg>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={String(row[keyField])}
              className={`
                border-b border-border-subtle/50 transition-colors duration-150
                ${onRowClick ? "cursor-pointer" : ""}
                hover:bg-accent-muted/50
              `}
              style={{ animationDelay: `${i * 30}ms` }}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col) => (
                <td key={col.key} className="py-3 px-4 text-sm font-body">
                  {col.render
                    ? col.render(row)
                    : <span className="text-text-secondary">{String(row[col.key] ?? "")}</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
