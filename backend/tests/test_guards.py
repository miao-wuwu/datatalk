r"""护栏与多轮追问的单元测试（不依赖模型：LLM 调用全部被替换）。

跑法：cd backend，然后 ..\.venv\Scripts\python.exe -m pytest tests -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import config, db, pipeline  # noqa: E402


# ---------------------------------------------------------------- 静态校验
class TestStaticGuard:
    def test_select_ok(self) -> None:
        assert db.validate("select 1") == "select 1"

    def test_reject_write(self) -> None:
        with pytest.raises(db.SQLRejected):
            db.validate("delete from jobs")

    def test_reject_multi_statement(self) -> None:
        with pytest.raises(db.SQLRejected):
            db.validate("select 1; drop table jobs")

    def test_comment_cannot_hide_write(self) -> None:
        with pytest.raises(db.SQLRejected):
            db.validate("select 1 -- 无害的注释\ndelete from jobs")

    def test_comment_stripped_before_semicolon_check(self) -> None:
        assert db.validate("select 1 /* ; drop table jobs */")

    def test_cte_name_is_not_a_table(self) -> None:
        sql = (
            "WITH top_city AS (SELECT city, COUNT(*) AS n FROM jobs GROUP BY city) "
            "SELECT * FROM top_city ORDER BY n DESC LIMIT 3"
        )
        assert db.validate(sql)


# ---------------------------------------------------------------- 表白名单
class TestTableWhitelist:
    def test_default_allows_everything(self) -> None:
        assert "skills" in db.allowed_tables()

    def test_whitelist_blocks_other_tables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "ALLOWED_TABLES", ["jobs", "companies"])
        db._schema_cache = None
        try:
            db.run("SELECT COUNT(*) FROM jobs")
            with pytest.raises(db.SQLRejected) as exc:
                db.validate("SELECT COUNT(*) FROM skills")
            assert "白名单" in str(exc.value)
            assert "skills" not in db.schema_text()
        finally:
            db._schema_cache = None

    def test_unknown_whitelist_entry_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "ALLOWED_TABLES", ["nope"])
        db._schema_cache = None
        try:
            with pytest.raises(db.SQLRejected):
                db.allowed_tables()
        finally:
            db._schema_cache = None


# ---------------------------------------------------------------- 多轮追问
class _FakeLLM:
    """按调用顺序返回固定文本，记录每次请求的消息。"""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    async def __call__(self, messages, **kwargs):  # noqa: ANN001
        self.calls.append(messages)
        text = self.replies.pop(0) if self.replies else "SELECT 1 AS x"
        return {"text": text, "usage": {}, "model": "fake"}


def _run(question: str, history=None):
    return asyncio.run(pipeline.ask(question, history=history))


class TestRewrite:
    def test_rewrite_strips_quotes_and_keeps_first_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeLLM(['"上海有多少个岗位？"\n多余的解释'])
        monkeypatch.setattr(pipeline.llm, "chat", fake)
        out = asyncio.run(pipeline._rewrite("那上海呢？", [{"question": "北京有多少岗位？", "sql": "SELECT 1"}]))
        assert out == "上海有多少个岗位？"

    def test_rewrite_without_history_is_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeLLM([])
        monkeypatch.setattr(pipeline.llm, "chat", fake)
        assert asyncio.run(pipeline._rewrite("北京有多少岗位？", [])) == "北京有多少岗位？"
        assert fake.calls == []


class TestAskWithHistory:
    def test_rewritten_question_drives_sql(self, monkeypatch: pytest.MonkeyPatch) -> None:
        replies = [
            "上海有多少个岗位？",                                   # 改写
            "SELECT COUNT(*) AS 岗位数 FROM jobs WHERE city = '上海'",  # 生成
        ]
        monkeypatch.setattr(pipeline.llm, "chat", _FakeLLM(replies))
        result = _run("那上海呢？", history=[{"question": "北京有多少个岗位？", "sql": "SELECT COUNT(*) FROM jobs WHERE city='北京'"}])
        assert result.rewritten == "上海有多少个岗位？"
        assert result.steps[0]["name"] == "理解追问"
        assert "上海" in result.sql
        assert result.error is None
        assert result.rows[0][0] > 0

    def test_rewrite_failure_falls_back_to_original(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Boom:
            async def __call__(self, messages, **kwargs):  # noqa: ANN001
                raise pipeline.llm.LLMError("模型挂了")

        monkeypatch.setattr(pipeline.llm, "chat", Boom())
        result = _run("那上海呢？", history=[{"question": "北京有多少个岗位？", "sql": "SELECT 1"}])
        assert result.rewritten is None
        assert result.steps[0]["status"] == "skipped"
        assert result.error  # 生成阶段也失败，但没有抛异常

    def test_no_history_keeps_single_turn_flow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pipeline.llm, "chat", _FakeLLM(["SELECT COUNT(*) AS n FROM jobs"]))
        result = _run("有多少个岗位？")
        assert result.rewritten is None
        assert result.steps[0]["name"] == "生成 SQL"


# ---------------------------------------------------------------- 语义校验
class TestSemanticLint:
    def test_extra_education_filter_is_flagged(self) -> None:
        issues = pipeline.lint_semantics("SELECT COUNT(*) FROM jobs WHERE education = '不限'", "有多少个实习岗位")
        assert any("education" in i for i in issues)

    def test_mentioned_skill_must_use_job_skills(self) -> None:
        issues = pipeline.lint_semantics("SELECT COUNT(*) FROM jobs WHERE title LIKE '%Python%'", "招 Python 的岗位")
        assert any("job_skills" in i for i in issues)

    def test_group_by_city_needs_not_null(self) -> None:
        issues = pipeline.lint_semantics(
            "SELECT city, COUNT(*) FROM jobs GROUP BY city ORDER BY 2 DESC", "各城市岗位数"
        )
        assert any("IS NOT NULL" in i for i in issues)

    def test_two_skills_with_and_is_flagged(self) -> None:
        sql = (
            "SELECT COUNT(*) FROM jobs JOIN job_skills js ON js.job_id=jobs.id "
            "JOIN skills s ON s.id=js.skill_id WHERE s.name='Python' AND s.name='Agent'"
        )
        assert any("同时" in i for i in pipeline.lint_semantics(sql, "同时要 Python 和 Agent"))


# ---------------------------------------------------------------- 结果解读
class TestAnswerAndChart:
    def test_kpi_for_single_column(self) -> None:
        assert pipeline.infer_chart(["岗位数"], [[594]])["type"] == "kpi"

    def test_bar_for_many_rows(self) -> None:
        rows = [[f"c{i}", i] for i in range(20)]
        assert pipeline.infer_chart(["城市", "岗位数"], rows)["type"] == "bar"

    def test_empty_result_has_hint(self) -> None:
        assert "没有查到" in pipeline.make_answer(["a"], [], 0, False)