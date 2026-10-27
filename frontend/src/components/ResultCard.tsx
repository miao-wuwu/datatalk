import { useState } from "react";
import type { AskResult } from "../types";
import { ChartView } from "./ChartView";
import { ResultTable } from "./ResultTable";
import { SqlCard } from "./SqlCard";
import { StepTimeline } from "./StepTimeline";

const CONFIDENCE: Record<string, { text: string; cls: string }> = {
  high: { text: "一次生成即正确", cls: "ok" },
  medium: { text: "经自动修正", cls: "warn" },
  low: { text: "未得到可靠结果", cls: "err" },
};

export function ResultCard({
  result,
  onRunSql,
}: {
  result: AskResult;
  onRunSql: (sql: string) => void | Promise<void>;
}) {
  const hasChart = !!result.chart && result.chart.type !== "table" && (result.chart.data?.length ?? 0) > 0;
  const [tab, setTab] = useState<"chart" | "table">(hasChart ? "chart" : "table");
  const conf = CONFIDENCE[result.confidence] ?? CONFIDENCE.medium;

  return (
    <article className="card">
      <header className="card-head">
        <h3>{result.question}</h3>
        <span className={`badge ${conf.cls}`}>{conf.text}</span>
        {result.attempts > 0 && <span className="badge muted">自修复 {result.attempts} 次</span>}
      </header>

      <p className="answer">{result.answer}</p>

      <StepTimeline steps={result.steps} />

      {result.chart?.type === "kpi" && (
        <div className="kpi">
          <span className="kpi-value">{String(result.chart.value ?? "—")}</span>
          <span className="kpi-label">{result.chart.label}</span>
        </div>
      )}

      {hasChart && (
        <div className="tabs">
          <button type="button" className={tab === "chart" ? "tab active" : "tab"} onClick={() => setTab("chart")}>
            图表
          </button>
          <button type="button" className={tab === "table" ? "tab active" : "tab"} onClick={() => setTab("table")}>
            表格 · {result.row_count} 行
          </button>
        </div>
      )}

      {hasChart && tab === "chart" ? (
        <ChartView spec={result.chart!} />
      ) : (
        <ResultTable columns={result.columns} rows={result.rows} truncated={result.truncated} />
      )}

      <SqlCard sql={result.sql} onRun={onRunSql} />
    </article>
  );
}