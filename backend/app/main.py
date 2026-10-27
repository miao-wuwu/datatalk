"""DataTalk 后端 API。

启动：uvicorn app.main:app --reload --port 8100（在 backend/ 目录下）
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, llm, pipeline

app = FastAPI(
    title="DataTalk",
    version="0.2.0",
    description="自然语言查数据库：NL2SQL + 三道校验 + 自修复 + 多轮追问",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXAMPLES = [
    "北京招 Python 实习的公司有哪些？",
    "各城市的平均日薪是多少？",
    "招大模型岗位最多的 10 家公司",
    "本科和硕士岗位的平均薪资对比",
    "要求 React 的岗位城市分布",
    "日薪超过 300 元的岗位有多少个？",
    "同时要求 Python 和大模型的岗位",
    "每周要求 5 天的岗位占比",
]


class HistoryTurn(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    sql: str = Field(default="", max_length=4000)


class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    history: list[HistoryTurn] | None = Field(default=None, max_length=config.HISTORY_TURNS)


class SQLIn(BaseModel):
    sql: str = Field(..., min_length=1, max_length=4000)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "db": config.DB_PATH.name,
        "stats": db.stats(),
        "llm": await llm.health(),
        "model": config.LLM_MODEL,
    }


@app.get("/api/examples")
def examples() -> dict:
    return {"examples": EXAMPLES}


@app.get("/api/schema")
def schema() -> dict:
    return {"schema": db.schema_text()}


@app.post("/api/ask")
async def ask(body: AskIn) -> dict:
    history = [t.model_dump() for t in body.history] if body.history else None
    try:
        result = await pipeline.ask(body.question, history=history)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=f"模型服务异常：{exc}") from exc
    # 失败也返回 200：把已跑过的步骤交给前端，用户能看见卡在哪一步
    return result.to_dict()


@app.post("/api/sql")
def run_sql(body: SQLIn) -> dict:
    try:
        qr = db.run(body.sql)
    except db.SQLRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"执行失败：{exc}") from exc
    out = qr.to_dict()
    out["chart"] = pipeline.infer_chart(qr.columns, qr.rows)
    return out


# ---------------------------------------------------------------- 静态前端
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")