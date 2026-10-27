"""数据库访问层：只读执行 + 安全校验 + schema 自省。

设计要点：
- 连接用 `mode=ro` URI 打开，再加 `PRAGMA query_only`，双保险。
- 只允许单条 SELECT / WITH 语句，关键字黑名单兜底。
- 用 progress_handler 做超时中断，避免一条笛卡尔积把服务拖死。
- 结果统一转成 JSON 友好类型。
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from . import config

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|replace|reindex|trigger|begin|commit|rollback)\b",
    re.I,
)
ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.I)


class SQLRejected(ValueError):
    """SQL 未通过静态校验。"""


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    elapsed_ms: int = 0
    sql: str = ""

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "elapsed_ms": self.elapsed_ms,
            "sql": self.sql,
        }


def connect() -> sqlite3.Connection:
    if not config.DB_PATH.exists():
        raise FileNotFoundError(f"数据库不存在：{config.DB_PATH}（先跑 scripts/seed_db.py）")
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON")
    con.row_factory = sqlite3.Row
    return con


def validate(sql: str) -> str:
    """静态校验，返回清洗后的 SQL；不合格抛 SQLRejected。"""
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise SQLRejected("SQL 为空")
    # 去掉注释，避免用注释藏关键字
    clean = re.sub(r"--[^\n]*", " ", text)
    clean = re.sub(r"/\*.*?\*/", " ", clean, flags=re.S)
    if ";" in clean:
        raise SQLRejected("只允许单条语句（检测到分号）")
    if not ALLOWED_START.search(clean):
        raise SQLRejected("只允许 SELECT / WITH 查询")
    hit = FORBIDDEN.search(clean)
    if hit:
        raise SQLRejected(f"包含禁用的关键字：{hit.group(0).upper()}")
    return text


def run(sql: str, max_rows: int | None = None, timeout: float | None = None) -> QueryResult:
    sql = validate(sql)
    max_rows = max_rows or config.MAX_ROWS
    timeout = timeout or config.QUERY_TIMEOUT

    con = connect()
    started = time.perf_counter()
    deadline = started + timeout
    steps = {"n": 0}

    def _guard() -> int:
        steps["n"] += 1
        if steps["n"] % 2000 == 0 and time.perf_counter() > deadline:
            return 1  # 非 0 即中断
        return 0

    con.set_progress_handler(_guard, 5000)
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.OperationalError as exc:
        msg = str(exc)
        if "interrupted" in msg:
            raise TimeoutError(f"查询超过 {timeout:.0f}s 被中断，请缩小范围") from exc
        raise
    finally:
        con.set_progress_handler(None, 0)
        con.close()

    elapsed = int((time.perf_counter() - started) * 1000)
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return QueryResult(
        columns=columns,
        rows=[list(r) for r in rows],
        row_count=len(rows),
        truncated=truncated,
        elapsed_ms=elapsed,
        sql=sql,
    )


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 2)
    return v


SAMPLES: dict[str, list[str]] = {
    "companies.city": ["北京", "上海", "深圳"],
    "companies.industry": ["互联网", "AI", "汽车"],
    "jobs.city": ["北京", "上海", "深圳"],
    "jobs.education": ["本科", "硕士", "不限"],
    "skills.category": ["前端", "后端", "AI", "数据", "工程", "算法", "测试", "硬件"],
}


def schema_text() -> str:
    """给模型看的 schema 说明：DDL + 行数 + 关键枚举值。"""
    con = connect()
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        lines: list[str] = []
        for t in tables:
            cols = con.execute(f"PRAGMA table_info({t})").fetchall()
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            col_defs = []
            for c in cols:
                name, ctype = c[1], c[2]
                extra = ""
                if f"{t}.{name}" in SAMPLES:
                    extra = "  -- 例：" + " / ".join(SAMPLES[f"{t}.{name}"])
                col_defs.append(f"    {name} {ctype}{extra}")
            lines.append(f"  {t}（{n} 行）")
            lines.extend(col_defs)
    finally:
        con.close()
    return "\n".join(lines)


def stats() -> dict:
    con = connect()
    try:
        return {
            "jobs": con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "companies": con.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
            "skills": con.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
            "with_salary": con.execute("SELECT COUNT(*) FROM jobs WHERE salary_avg IS NOT NULL").fetchone()[0],
        }
    finally:
        con.close()


# ---------------------------------------------------------------- 语义校验
_schema_cache: dict | None = None


def table_columns() -> dict[str, list[str]]:
    global _schema_cache
    if _schema_cache is None:
        con = connect()
        try:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )]
            _schema_cache = {t: [c[1] for c in con.execute(f"PRAGMA table_info({t})")] for t in tables}
        finally:
            con.close()
    return _schema_cache


def skill_names() -> list[str]:
    con = connect()
    try:
        return [r[0] for r in con.execute("SELECT name FROM skills ORDER BY id")]
    finally:
        con.close()


def industry_values() -> list[str]:
    con = connect()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT industry FROM companies WHERE industry IS NOT NULL ORDER BY industry")]
    finally:
        con.close()


def source_values() -> list[str]:
    con = connect()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL ORDER BY source")]
    finally:
        con.close()


_EDU_OK = {"本科", "硕士", "大专", "博士", "不限"}


def lint(sql: str) -> list[str]:
    """在真正执行前做语义校验：表/列是否存在、枚举值是否合法。

    比"执行报错再修"更早拦住问题，也避免把 '实习生' 塞进 education 这类荒谬条件。
    """
    issues: list[str] = []
    tables = table_columns()
    lowered = sql.lower()

    used_tables = re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", lowered)
    for t in used_tables:
        if t not in tables:
            issues.append(f"表 {t} 不存在（可用：{', '.join(tables)}）")

    # 别名映射：table [AS] alias
    alias_map: dict[str, str] = {}
    for m in re.finditer(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)(?:\s+(?:as\s+)?([a-z_][a-z0-9_]*))?", lowered):
        table, alias = m.group(1), m.group(2)
        if table in tables:
            alias_map[table] = table
            if alias and alias not in {"where", "on", "group", "order", "limit", "join", "left", "inner"}:
                alias_map[alias] = table

    for m in re.finditer(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", lowered):
        alias, col = m.group(1), m.group(2)
        table = alias_map.get(alias)
        if table and col not in tables[table]:
            issues.append(f"列 {alias}.{col} 不存在（{table} 的列：{', '.join(tables[table])}）")

    # 教育/技能枚举值校验
    for m in re.finditer(r"education\s*=\s*'([^']*)'", sql, re.I):
        if m.group(1) not in _EDU_OK:
            issues.append(f"education 只能取 {sorted(_EDU_OK)}，不能是 '{m.group(1)}'")
    known = {s.lower() for s in skill_names()}
    for m in re.finditer(r"\bskills?\.name\s*=\s*'([^']*)'", sql, re.I):
        if m.group(1).lower() not in known:
            issues.append(f"skills.name 没有 '{m.group(1)}'（可用：{', '.join(skill_names())}）")
    for m in re.finditer(r"\bskills?\.category\s*=\s*'([^']*)'", sql, re.I):
        cats = {"前端", "后端", "ai", "数据", "工程", "算法", "测试", "硬件"}
        if m.group(1).lower() not in cats:
            issues.append(f"skills.category 没有 '{m.group(1)}'")
    return issues