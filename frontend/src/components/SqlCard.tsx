import { useState } from "react";

export function SqlCard({
  sql,
  onRun,
}: {
  sql: string;
  onRun?: (sql: string) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sql);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="sql-card">
      <div className="sql-head">
        <button type="button" className="sql-toggle" onClick={() => setOpen((v) => !v)}>
          <span className={`caret ${open ? "open" : ""}`}>▸</span> SQL
        </button>
        <div className="sql-actions">
          <button type="button" className="ghost" onClick={copy}>
            {copied ? "已复制" : "复制"}
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setOpen(true);
              setEditing((v) => !v);
              setDraft(sql);
            }}
          >
            {editing ? "取消" : "编辑"}
          </button>
        </div>
      </div>

      {open &&
        (editing ? (
          <div className="sql-edit">
            <textarea value={draft} spellCheck={false} onChange={(e) => setDraft(e.target.value)} />
            <div className="sql-edit-actions">
              <button
                type="button"
                className="primary sm"
                onClick={() => {
                  setEditing(false);
                  void onRun?.(draft);
                }}
              >
                执行
              </button>
            </div>
          </div>
        ) : (
          <pre className="sql-body">
            <code>{sql}</code>
          </pre>
        ))}
    </div>
  );
}