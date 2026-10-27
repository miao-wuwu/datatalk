import { lazy, Suspense, useState } from "react";
import type { AskResult } from "../types";
import { ResultTable } from "./ResultTable";
import { SqlCard } from "./SqlCard";
import { StepTimeline } from "./StepTimeline";

// echarts 有 1MB，首屏不需要它：等用户点开图表再加载
const ChartView = lazy(() =>
  import("./ChartView").then((m) => ({ default: m.ChartView })),
);

const CONFIDENCE: Record<string, { text: string; cls: string }> = {
  high: { text: "一次生成即正确", cls: "ok" },
  medium: { text: "经自动修正", cls: "warn" },
  low: { text: "未得到可靠结果", cls: "err" },
};

export function ResultCard({
  result,
  onRunSql,
  onFollowUp,
}: {
  result: AskResult;
  onRunSql: (sql: string) => void | Promise<void>;
  onFollowUp?: (result: AskResult) => void;
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

      {result.rewritten && <p className="rewritten">已理解为：{result.rewritten}</p>}

      {result.error && <p className="card-error">{result.error}</p>}

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
        <Suspense fallback={<div className="chart-loading">图表加载中…</div>}>
          <ChartView spec={result.chart!} />
        </Suspense>
      ) : (
        <ResultTable columns={result.columns} rows={result.rows} truncated={result.truncated} />
      )}

      <SqlCard sql={result.sql} onRun={onRunSql} />

      {onFollowUp && (
        <div className="card-foot">
          <button type="button" className="ghost" onClick={() => onFollowUp(result)}>
            在此追问
          </button>
          <span className="muted">把这一问当上下文，接着问「那上海呢」「只看本科的」</span>
        </div>
      )}
    </article>
  );
}