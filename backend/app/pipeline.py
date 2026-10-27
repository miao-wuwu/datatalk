"""NL2SQL 主流程：生成 → 校验 → 执行 → 失败自修复 → 图表/结论。

每一步都记进 steps，前端按时间线展示——「它为什么给出这个结果」比结果本身更重要。
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from . import config, db, llm, semantic

SYSTEM = """你是 SQLite 查询专家。把用户的中文问题翻译成一条可执行的 SELECT 语句。

硬性规则：
1. 只输出 SQL，不要解释、不要 Markdown 代码块之外的文字。
2. 只能查询，禁止 INSERT/UPDATE/DELETE/DROP/CREATE/ALTER 等写操作。
3. 只能用下面给出的表和列，不要编造字段。
4. 输出列用中文别名（AS 中文名），便于直接展示。
5. 结果有可能很多时加 LIMIT 50；按某维度聚合排序的用 LIMIT 20。
6. 计算薪资必须排除 salary_avg IS NULL 的行。
7. 字符串比较用 = 或 LIKE，城市值用简体中文（北京/上海/深圳…）。
8. **不要添加问题里没有提到的过滤条件**。特别注意：不要因为"实习"就给 education 加条件，不要给 title 加精确匹配。
9. 分组统计必须 ORDER BY 指标 DESC；按城市分组要加 `WHERE city IS NOT NULL`。
10. 按技能筛选时，用 job_skills 关联 skills.name（取上面列出的准确写法），不要用 title LIKE。
11. 如果问题信息不足（比如没说什么城市却要"这个城市"），按最常见口径处理，并在 SQL 注释里说明。
"""

REPAIR = """刚才的 SQL 执行失败了。

SQL：
{sql}

错误信息：
{error}

请修正后只输出一条新的 SELECT 语句。要求同上：只输出 SQL，不要解释。"""


@dataclass
class Step:
    name: str
    status: str            # ok | error | skipped
    detail: str = ""
    ms: int = 0


@dataclass
class AskResult:
    question: str
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    chart: dict | None = None
    answer: str = ""
    steps: list[dict] = field(default_factory=list)
    attempts: int = 0
    confidence: str = "high"
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def extract_sql(text: str) -> str:
    """从模型输出里抠出 SQL：优先代码块，其次第一段 select/with。"""
    if not text:
        return ""
    fence = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    body = fence.group(1) if fence else text
    m = re.search(r"\b(with|select)\b.*", body, re.S | re.I)
    if not m:
        return ""
    sql = m.group(0).strip()
    # 截掉可能跟在后面的解释文字：以分号或空行后的中文开头行为界
    sql = re.split(r";\s*\n", sql)[0].strip()
    sql = re.split(r"\n\s*\n(?=[\u4e00-\u9fff])", sql)[0].strip()
    return sql.rstrip(";").strip()


async def _generate(question: str) -> tuple[str, dict]:
    examples = semantic.pick_examples(question, k=2)
    shots = "\n\n".join(f"问题：{nl}\nSQL：\n{sql}" for nl, sql in examples)
    user = (
        f"数据库结构：\n{db.schema_text()}\n\n"
        f"{semantic.glossary_text()}\n\n"
        f"参考示例：\n{shots}\n\n"
        f"问题：{question}\nSQL："
    )
    out = await llm.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=600,
        stop=["\n\n\n"],
    )
    return extract_sql(out["text"]), out.get("usage") or {}


async def _repair(question: str, sql: str, error: str) -> str:
    user = (
        f"数据库结构：\n{db.schema_text()}\n\n"
        f"{semantic.glossary_text()}\n\n"
        f"原始问题：{question}\n\n"
        + REPAIR.format(sql=sql, error=error[:600])
    )
    out = await llm.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=600,
    )
    return extract_sql(out["text"])


# ---------------------------------------------------------------- 语义校验
def lint_semantics(sql: str, question: str) -> list[str]:
    """生成后的语义检查：过滤条件是否问过、聚合是否排序。

    3B 模型最常见的错误不是语法，而是"自作主张加条件"：
    问「北京招 Python 的公司」它给你加个 education='不限'，结果直接少一半。
    """
    issues: list[str] = []

    for col, val in re.findall(r"\b(education|city)\s*=\s*'([^']*)'", sql, re.I):
        token = val.strip()
        if token and token not in question:
            issues.append(f"问题里没提 {col}='{token}'，不要自己加过滤条件")

    names = [
        m for m in re.findall(r"\bskills?\.name\s*(?:=|in)\s*\(?([^)\n]*)", sql, re.I)
    ]
    if names:
        literals = re.findall(r"'([^']*)'", names[0])
        if literals and not any(lit in question for lit in literals):
            issues.append(f"问题里没提技能 {literals}，不要自己加技能过滤")

    if re.search(r"\bgroup\s+by\b", sql, re.I) and not re.search(r"\border\s+by\b", sql, re.I):
        issues.append("这是分组统计，请加 ORDER BY 指标 DESC 让结果有序")

    if re.search(r"\bgroup\s+by\s+(?:\w+\.)?city\b", sql, re.I) and not re.search(r"city\s+is\s+not\s+null", sql, re.I):
        issues.append("按城市统计时请加 WHERE city IS NOT NULL，避免出现空城市分组")

    # 问题里点名了技能，却用 title LIKE 去匹配（3B 的高频偷懒写法）
    if "job_skills" not in sql.lower():
        hit = next((name for name in db.skill_names() if name in question), None)
        if hit:
            issues.append(f"问题里提到了技能「{hit}」，请用 job_skills 关联 skills.name = '{hit}' 过滤，不要用 title LIKE")

    return issues


# ---------------------------------------------------------------- 图表推断
def infer_chart(columns: list[str], rows: list[list[Any]]) -> dict | None:
    if not rows or not columns:
        return None
    n_num = sum(1 for i in range(min(len(columns), 6))
                if all(isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in rows if len(r) > i))
    if len(columns) == 1:
        return {"type": "kpi", "label": columns[0], "value": rows[0][0]}
    if len(columns) == 2 and n_num >= 1:
        x = [str(r[0]) for r in rows]
        y = [r[1] for r in rows]
        is_date = all(re.match(r"^\d{4}[-/]\d{1,2}", str(v)) for v in x[:3])
        if len(rows) <= 6 and not is_date:
            return {"type": "pie", "x": columns[0], "y": columns[1], "data": [{"name": a, "value": b} for a, b in zip(x, y)]}
        return {"type": "line" if is_date else "bar", "x": columns[0], "y": columns[1],
                "data": [{"name": a, "value": b} for a, b in zip(x, y)]}
    return {"type": "table"}


def make_answer(columns: list[str], rows: list[list[Any]], row_count: int, truncated: bool) -> str:
    if not rows:
        return "没有查到符合条件的数据。可以换个条件试试（比如放宽城市或技能要求）。"
    parts = [f"共 {row_count} 条结果" + ("（已截断，只显示前 200 条）" if truncated else "") + "。"]
    if len(columns) >= 2:
        head = [str(r[0]) if r[0] is not None else "未知" for r in rows[:3]]
        second = [r[1] for r in rows[:3]]
        if all(isinstance(v, (int, float)) for v in second):
            parts.append(
                f"排在前面的依次是：{'、'.join(f'{h}（{v}）' for h, v in zip(head, second))}。"
            )
        else:
            parts.append("前几条结果：" + "；".join(
                "，".join(f"{c}={v}" for c, v in zip(columns, r)) for r in rows[:2]
            ) + "。")
    else:
        parts.append(f"{columns[0]} = {rows[0][0]}。")
    return "".join(parts)


async def ask(question: str, max_rows: int | None = None) -> AskResult:
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")
    if len(question) > config.MAX_QUESTION_CHARS:
        raise ValueError(f"问题太长了（上限 {config.MAX_QUESTION_CHARS} 字）")

    result = AskResult(question=question)
    t0 = time.perf_counter()

    def add(name: str, status: str, detail: str, since: float) -> None:
        result.steps.append(asdict(Step(name, status, detail, int((time.perf_counter() - since) * 1000))))

    # 1) 生成
    s = time.perf_counter()
    try:
        sql, usage = await _generate(question)
    except llm.LLMError as exc:
        add("生成 SQL", "error", str(exc), s)
        result.error = str(exc)
        result.confidence = "low"
        return result
    if not sql:
        add("生成 SQL", "error", "模型没有返回可识别的 SQL", s)
        result.error = "模型没有返回可识别的 SQL"
        result.confidence = "low"
        return result
    add("生成 SQL", "ok", sql.splitlines()[0][:80], s)
    result.sql = sql
    result.attempts = 0

    # 2) 语义校验 → 执行 → 自修复
    current, last_error = sql, None
    while True:
        issues = db.lint(current) + lint_semantics(current, question)
        s = time.perf_counter()
        if issues:
            last_error = "语义校验未通过：" + "；".join(issues[:3])
            add("语义校验", "error", last_error, s)
        else:
            add("语义校验", "ok", "表 / 列 / 枚举值均合法", s)
            s = time.perf_counter()
            try:
                qr = db.run(current, max_rows=max_rows or config.MAX_ROWS)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                add("执行 SQL", "error", last_error[:200], s)
            else:
                add("执行 SQL", "ok", f"{qr.row_count} 行 / {qr.elapsed_ms} ms", s)
                result.columns = qr.columns
                result.rows = qr.rows
                result.row_count = qr.row_count
                result.truncated = qr.truncated
                break

        # 走到这里说明失败：尝试修复
        result.attempts += 1
        if result.attempts > config.MAX_REPAIR:
            result.error = f"执行失败且自修复次数用尽：{last_error}"
            result.confidence = "low"
            return result
        s = time.perf_counter()
        try:
            fixed = await _repair(question, current, last_error)
        except llm.LLMError as exc:
            result.error = str(exc)
            add("自修复", "error", str(exc), s)
            result.confidence = "low"
            return result
        if not fixed or fixed == current:
            add("自修复", "error", "模型没有给出可用的修正", s)
            result.error = "自修复失败：模型未能修正 SQL"
            result.confidence = "low"
            return result
        add("自修复", "ok", fixed.splitlines()[0][:80], s)
        current = fixed
        result.sql = fixed

    # 3) 结果解读
    s = time.perf_counter()
    result.chart = infer_chart(result.columns, result.rows)
    result.answer = make_answer(result.columns, result.rows, result.row_count, result.truncated)
    add("结果解读", "ok", result.answer[:120], s)

    result.confidence = "high" if result.attempts == 0 else "medium"
    total = int((time.perf_counter() - t0) * 1000)
    result.steps.append(asdict(Step("总耗时", "ok", f"{total} ms", total)))
    return result