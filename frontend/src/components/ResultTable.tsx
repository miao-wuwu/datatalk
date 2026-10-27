const MAX_ROWS = 100;

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  return String(value);
}

export function ResultTable({
  columns,
  rows,
  truncated,
}: {
  columns: string[];
  rows: unknown[][];
  truncated?: boolean;
}) {
  if (!columns.length) return null;
  const shown = rows.slice(0, MAX_ROWS);

  return (
    <div className="table-wrap">
      <table className="result-table">
        <thead>
          <tr>
            <th className="idx">#</th>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i}>
              <td className="idx">{i + 1}</td>
              {row.map((v, j) => (
                <td key={j} className={typeof v === "number" ? "num" : undefined}>
                  {cell(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {(truncated || rows.length > shown.length) && (
        <div className="table-note">
          只显示前 {shown.length} 行{truncated ? "（结果被截断）" : ""}
        </div>
      )}
    </div>
  );
}