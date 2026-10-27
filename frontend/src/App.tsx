import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "./api";
import { ResultCard } from "./components/ResultCard";
import type { AskResult, Health } from "./types";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [examples, setExamples] = useState<string[]>([]);
  const [results, setResults] = useState<AskResult[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.health().then(setHealth).catch(() => setHealth(null));
    void api.examples().then((r) => setExamples(r.examples)).catch(() => setExamples([]));
  }, []);

  const history = useMemo(() => {
    const seen = new Set<string>();
    return results.map((r) => r.question).filter((q) => (seen.has(q) ? false : (seen.add(q), true)));
  }, [results]);

  const submit = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || busy) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api.ask(q);
        setResults((prev) => [result, ...prev]);
        setQuestion("");
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setBusy(false);
      }
    },
    [busy],
  );

  const runManualSql = useCallback(async (sql: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.runSql(sql);
      const manual: AskResult = {
        question: "手写 SQL 执行",
        sql: r.sql,
        columns: r.columns,
        rows: r.rows,
        row_count: r.row_count,
        truncated: r.truncated,
        chart: r.chart,
        answer: `执行完成，${r.row_count} 行，耗时 ${r.elapsed_ms} ms。`,
        steps: [
          { name: "执行 SQL", status: "ok", detail: `${r.row_count} 行 / ${r.elapsed_ms} ms`, ms: r.elapsed_ms },
        ],
        attempts: 0,
        confidence: "high",
      };
      setResults((prev) => [manual, ...prev]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">▚</span>
          <div>
            <h1>DataTalk</h1>
            <p>用中文问数据库，自动生成 SQL、执行、给结论</p>
          </div>
        </div>
        <div className="stats">
          {health && (
            <>
              <span className="stat">
                <b>{health.stats.jobs.toLocaleString()}</b> 岗位
              </span>
              <span className="stat">
                <b>{health.stats.companies}</b> 公司
              </span>
              <span className="stat">
                <b>{health.stats.skills}</b> 技能
              </span>
              <span className={`stat model ${health.llm.ok ? "up" : "down"}`}>
                {health.llm.ok ? "模型就绪" : "模型离线"} · {health.model}
              </span>
            </>
          )}
        </div>
      </header>

      <main className="layout">
        <aside className="sidebar">
          <section>
            <h2>示例问题</h2>
            <div className="chips">
              {examples.map((ex) => (
                <button key={ex} type="button" className="chip" onClick={() => void submit(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          </section>

          {history.length > 0 && (
            <section>
              <h2>历史</h2>
              <ul className="history">
                {history.slice(0, 12).map((q) => (
                  <li key={q}>
                    <button type="button" onClick={() => void submit(q)}>
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="about">
            <h2>数据说明</h2>
            <p>
              演示库来自真实爬取的实习岗位（实习僧 + 牛客），已清洗：公司 570 家、岗位 1,618 条、技能 38 类。
            </p>
            <p>只读连接 + 单条 SELECT 校验 + 8 秒超时，改不了库也拖不死服务。</p>
          </section>
        </aside>

        <section className="panel">
          <form
            className="ask-bar"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(question);
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="比如：北京招 Python 的公司里，哪家给的钱最多？"
              autoFocus
            />
            <button type="submit" className="primary" disabled={busy || !question.trim()}>
              {busy ? "查询中…" : "提问"}
            </button>
          </form>

          {error && <div className="banner error">{error}</div>}

          {busy && (
            <div className="banner loading">
              <span className="spinner" /> 正在把问题翻译成 SQL…
            </div>
          )}

          {results.length === 0 && !busy && (
            <div className="empty">
              <p>问一句人话，得到 SQL、表格和图表。</p>
              <p className="muted">试试左边的示例，或直接输入「上海平均日薪多少」。</p>
            </div>
          )}

          <div className="results">
            {results.map((r, i) => (
              <ResultCard key={`${r.question}-${i}`} result={r} onRunSql={runManualSql} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}