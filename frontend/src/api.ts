import type { AskResult, Health, HistoryTurn, SqlResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!resp.ok) {
    let message = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      const detail = body?.detail;
      message = typeof detail === "string" ? detail : detail?.message || JSON.stringify(detail);
    } catch {
      /* 保底用状态码 */
    }
    throw new Error(message);
  }
  return (await resp.json()) as T;
}

export const health = () => request<Health>("/api/health");

export const examples = () => request<{ examples: string[] }>("/api/examples");

export const ask = (question: string, history?: HistoryTurn[]) =>
  request<AskResult>("/api/ask", {
    method: "POST",
    body: JSON.stringify(history && history.length ? { question, history } : { question }),
  });

export const runSql = (sql: string) =>
  request<SqlResult>("/api/sql", { method: "POST", body: JSON.stringify({ sql }) });