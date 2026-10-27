export interface Step {
  name: string;
  status: "ok" | "error" | "skipped";
  detail: string;
  ms: number;
}

export interface ChartDatum {
  name: string;
  value: number;
}

export interface ChartSpec {
  type: "kpi" | "bar" | "line" | "pie" | "table";
  label?: string;
  value?: unknown;
  x?: string;
  y?: string;
  data?: ChartDatum[];
}

export interface AskResult {
  question: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  chart: ChartSpec | null;
  answer: string;
  steps: Step[];
  attempts: number;
  confidence: "high" | "medium" | "low";
  error?: string | null;
  rewritten?: string | null;
}

export interface HistoryTurn {
  question: string;
  sql: string;
}

export interface SqlResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  elapsed_ms: number;
  sql: string;
  chart: ChartSpec | null;
}

export interface Health {
  ok: boolean;
  db: string;
  stats: { jobs: number; companies: number; skills: number; with_salary: number };
  llm: { ok: boolean; model?: string; status?: number; error?: string };
  model: string;
}