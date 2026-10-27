"""跑 100+ 题金标准评测：比较结果集，而不是比较 SQL 字符串。

用法（在 D:\\datatalk\\backend 下）：
    python -m scripts.eval_nl2sql                # 全量
    python -m scripts.eval_nl2sql --limit 20     # 先跑 20 题
    python -m scripts.eval_nl2sql --tag no-lint  # 报告标题后缀（ablation 用）

对比口径：
  strict   —— 行集合逐值相等（列顺序、列内顺序都要对）
  relaxed  —— 行内按值排序后比较（容忍列顺序不同），多列结果才用得上
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db, pipeline  # noqa: E402

EVAL_SET = ROOT / "data" / "eval_set.json"
OUT_JSON = ROOT / "data" / "eval_result.json"
OUT_MD = ROOT / "docs" / "eval-report.md"


def norm_cell(v):
    if isinstance(v, float):
        if v == int(v):
            return int(v)
        return round(v, 2)
    return v


def norm_rows(rows) -> list[tuple]:
    return [tuple(norm_cell(v) for v in row) for row in rows]


def cell_eq(a, b) -> bool:
    """数值允许 0.05 的误差（模型用 ROUND(x,1) 还是 ROUND(x,2) 不该判错）。"""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= 0.051
    return str(a).strip() == str(b).strip()


def row_eq(r1, r2, relaxed: bool = False) -> bool:
    if len(r1) != len(r2):
        return False
    if relaxed:
        r1 = tuple(sorted(r1, key=lambda x: str(x)))
        r2 = tuple(sorted(r2, key=lambda x: str(x)))
    return all(cell_eq(a, b) for a, b in zip(r1, r2))


def same_set(a, b, relaxed: bool = False) -> bool:
    if len(a) != len(b):
        return False
    pool = list(b)
    for row in a:
        for i, cand in enumerate(pool):
            if row_eq(row, cand, relaxed):
                pool.pop(i)
                break
        else:
            return False
    return True


async def one(case: dict) -> dict:
    t0 = time.perf_counter()
    try:
        res = await pipeline.ask(case["question"], max_rows=1000)
    except Exception as exc:  # noqa: BLE001
        return {"id": case["id"], "question": case["question"], "category": case["category"],
                "ok": False, "strict": False, "relaxed": False, "error": str(exc),
                "attempts": 0, "latency_ms": int((time.perf_counter() - t0) * 1000),
                "sql": "", "gold_sql": case["sql"], "kind": "exception"}
    gold = norm_rows(case["rows"])
    got = norm_rows(res.rows or [])
    strict = bool(res.rows) and same_set(gold, got)
    relaxed = strict or (bool(res.rows) and same_set(gold, got, relaxed=True))
    return {
        "id": case["id"], "category": case["category"], "question": case["question"],
        "ok": post_ok(res),
        "strict": strict, "relaxed": relaxed,
        "attempts": res.attempts, "confidence": res.confidence,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "error": res.error or "",
        "sql": res.sql or "", "gold_sql": case["sql"],
        "got_rows": len(got), "gold_rows": len(gold),
        "sample_got": got[:3], "sample_gold": gold[:3],
        "kind": "ok" if strict else ("relaxed" if relaxed else classify(res, got, gold)),
    }


def post_ok(res) -> bool:
    return not res.error


def classify(res, got, gold) -> str:
    if not res.rows:
        return "empty"
    if res.error:
        return "error"
    if len(got) != len(gold):
        return "row_count"
    if [len(r) for r in got] != [len(r) for r in gold]:
        return "col_count"
    return "values"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cases = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]
    print(f"评测 {len(cases)} 题 | 模型 {config.LLM_MODEL} | 语义校验 "
          f"{'开' if config.SEMANTIC_CHECK else '关'} | max_repair={config.MAX_REPAIR}", flush=True)

    results, t0 = [], time.perf_counter()
    for i, case in enumerate(cases, 1):
        r = await one(case)
        results.append(r)
        flag = "✓✓" if r["strict"] else ("✓~" if r["relaxed"] else "✗ ")
        print(f"[{i:3d}/{len(cases)}] {flag} {r['question'][:34]:<34} "
              f"{r['latency_ms']:>5}ms attempts={r['attempts']} {r['kind']}", flush=True)

    elapsed = time.perf_counter() - t0
    summary = summarize(results, elapsed)
    payload = {"config": {"model": config.LLM_MODEL, "semantic_check": config.SEMANTIC_CHECK,
                          "max_repair": config.MAX_REPAIR, "tag": args.tag},
               "summary": summary, "results": results}
    out = Path(args.out) if args.out else OUT_JSON
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(payload, out_md=OUT_MD if not args.tag else OUT_MD.with_name(f"eval-report-{args.tag}.md"))
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    return 0


def summarize(results: list[dict], elapsed: float) -> dict:
    n = len(results)
    strict = sum(r["strict"] for r in results)
    relaxed = sum(r["relaxed"] for r in results)
    first = sum(r["strict"] and r["attempts"] == 0 for r in results)
    repaired_ok = sum(r["strict"] and r["attempts"] > 0 for r in results)
    lat = [r["latency_ms"] for r in results]
    by_cat: dict[str, dict] = {}
    for r in results:
        c = by_cat.setdefault(r["category"], {"n": 0, "strict": 0, "relaxed": 0})
        c["n"] += 1
        c["strict"] += r["strict"]
        c["relaxed"] += r["relaxed"]
    return {
        "n": n,
        "strict_acc": round(strict / n, 4),
        "relaxed_acc": round(relaxed / n, 4),
        "first_pass_acc": round(first / n, 4),
        "repair_success": repaired_ok,
        "repair_attempts": sum(r["attempts"] for r in results),
        "avg_attempts": round(statistics.mean(r["attempts"] for r in results), 2),
        "avg_latency_ms": int(statistics.mean(lat)),
        "p95_latency_ms": int(sorted(lat)[int(n * 0.95) - 1]),
        "failures": {k: v for k, v in Counter(r["kind"] for r in results if not r["strict"]).items()},
        "by_category": by_cat,
        "elapsed_s": round(elapsed, 1),
    }


def write_report(payload: dict, out_md: Path) -> None:
    s, cfg = payload["summary"], payload["config"]
    n = s["n"]
    lines = [
        f"# DataTalk 评测报告{(' · ' + cfg['tag']) if cfg.get('tag') else ''}",
        "",
        f"- 模型：`{cfg['model']}`",
        f"- 语义校验：{'开启' if cfg['semantic_check'] else '关闭'}　自修复上限：{cfg['max_repair']}",
        f"- 题量：{n}　总耗时：{s['elapsed_s']}s",
        "",
        "## 总体",
        "",
        "| 指标 | 数值 | 说明 |",
        "| --- | --- | --- |",
        f"| 执行准确率（strict） | **{s['strict_acc'] * 100:.1f}%** | 结果集逐值相等 |",
        f"| 执行准确率（relaxed） | {s['relaxed_acc'] * 100:.1f}% | 容忍列顺序不同 |",
        f"| 首次生成准确率 | {s['first_pass_acc'] * 100:.1f}% | 一次生成即正确，无需修复 |",
        f"| 自修复救回 | {s['repair_success']} 题 | 修复后才对 |",
        f"| 平均修复轮次 | {s['avg_attempts']} | 含 0 次的题 |",
        f"| 平均延迟 / P95 | {s['avg_latency_ms']}ms / {s['p95_latency_ms']}ms | 端到端 |",
        "",
        "## 分类",
        "",
        "| 类别 | 题数 | strict | relaxed |",
        "| --- | --- | --- | --- |",
    ]
    for cat, c in sorted(s["by_category"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(f"| {cat} | {c['n']} | {c['strict'] / c['n'] * 100:.0f}% | {c['relaxed'] / c['n'] * 100:.0f}% |")
    if s["failures"]:
        lines += ["", "失败类型：" + "，".join(f"{k} {v} 题" for k, v in s["failures"].items())]

    fails = [r for r in payload["results"] if not r["strict"]]
    if fails:
        lines += ["", "## 失败样例（最多 12 条）", ""]
        for r in fails[:12]:
            lines += [
                f"### {r['id']}. {r['question']}",
                f"- 类型：`{r['kind']}`　行数 gold/got：{r['gold_rows']}/{r['got_rows']}　尝试：{r['attempts']}",
                f"- 金标准：`{(r['gold_sql'] or '')[:300]}`",
                f"- 模型：`{(r['sql'] or '')[:300]}`",
            ]
            if r.get("error"):
                lines.append(f"- 错误：{r['error'][:200]}")
            lines.append("")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))