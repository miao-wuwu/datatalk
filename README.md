# DataTalk · 用中文查数据库

> 输入一句人话 → 自动生成 SQL → 只读执行 → 失败自动修 → 给出表格和图表。

![结果示例](screenshots/result.png)

大多数「NL2SQL Demo」只做到「把模型生成的 SQL 打印出来」，一遇到字段名写错、聚合写错、加了不该加的过滤条件就崩。这个项目把重点放在**它出错的那 90%**：在 SQL 真正打到数据库之前，先过三道校验；执行失败时带着数据库的原始报错去修正；改不好就老实说改不好，而不是给一个看起来对的结果。

## 它长什么样

- 左边示例问题与历史，右边问答流
- 每个回答带**执行时间线**：生成 SQL → 语义校验 → 执行 → 结果解读，每步耗时与结果都可查
- 结果可切换「图表 / 表格」，SQL 可以展开、手改、重新执行
- 结果卡上标明这次是「一次生成即正确」还是「经自动修正」

## 三道护栏

| 层级 | 检查什么 | 拦掉的典型错误 |
| --- | --- | --- |
| 静态校验 | 单条语句、只允许 SELECT/WITH、关键字黑名单 | 模型顺手写出 `DROP`、多语句注入 |
| 语义校验 | 表/列是否存在、枚举值是否合法、是否加了问题里没提的过滤条件、按技能筛选是否用了 `job_skills` | `education='实习生'`、`city='帝都'`、问「北京 Python 岗」却加 `education='不限'` 把一半岗位过滤掉 |
| 执行校验 | 只读连接、8 秒超时、最多 200 行 | 笛卡尔积把服务拖死 |

任何一层不过，都会带着**具体原因**回到模型做自修复（默认最多 2 次）。修不好就返回失败原因，不编结果。

## 快速开始

```powershell
# 1) 后端（Python 3.11+）
cd D:\datatalk
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2) 构建演示库（数据来源见下）
.\.venv\Scripts\python.exe backend\scripts\seed_db.py

# 3) 起服务
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8100
# 打开 http://127.0.0.1:8100/ ；API 文档 http://127.0.0.1:8100/docs
```

前端开发模式（改样式/交互时用）：

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5174 ，/api 已代理到 8100
npm run build        # 产物给后端直接托管
```

## 配置

全部走环境变量（见 `.env.example`），默认接本机 Ollama：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | 任意 OpenAI 兼容端点：Ollama / DeepSeek / 百炼 |
| `LLM_MODEL` | `studymate-qwen` | 本机模型名 |
| `LLM_API_KEY` | 空 | 云端服务才需要 |
| `MAX_ROWS` | `200` | 单次返回上限 |
| `QUERY_TIMEOUT` | `8` | 单条查询超时（秒） |
| `MAX_REPAIR` | `2` | 自修复最大轮次 |

## 演示数据

库来自真实爬取的实习招聘 JD（实习僧 1,604 条 + 牛客 436 条，去重并清洗后 **1,618 条岗位 / 570 家公司 / 38 类技能**），清洗掉了「城市写成"可转正"」「日薪 2.5 元」这类脏数据（`backend/scripts/seed_db.py` 里可见规则）。

表结构：

```
companies(id, name, city, industry, job_count)
jobs(id, company_id, title, city, salary_min, salary_max, salary_avg,
     education, days_per_week, months, source, publish_date, url, jd_text)
skills(id, name, category)
job_skills(job_id, skill_id)
```

## 目录

```
backend/
  app/
    main.py       FastAPI 路由（/api/ask /api/sql /api/schema /api/health）
    pipeline.py   NL2SQL 主流程 + 语义校验 + 图表推断 + 结论生成
    db.py         只读执行、SQL 静态校验、schema 自省
    semantic.py   指标口径、同义词、few-shot 示例检索
    llm.py        OpenAI 兼容调用
  scripts/
    seed_db.py    从原始 JD JSON 构建演示库
frontend/         React + TS + Vite + ECharts
docs/             设计说明与评测报告
scripts/          CDP 截图等开发脚本
```

## 已知限制

- 本机 3B 模型（Qwen2.5-3B）在复杂多表聚合上仍会出错，靠自修复兜底；换 7B/云端模型质量会明显提升（见 `docs/设计说明.md`）
- 目前只支持单轮提问，不做多轮上下文改写
- 结果解读是规则模板，不是二次调用模型（牺牲一点自然度，换确定性和速度）

## 路线

- [x] 只读执行 + 三道校验 + 自修复
- [x] 图表/表格/时间线前端
- [ ] 100 题金标准评测集 + 自动判分（比结果集，不比 SQL 字符串）
- [ ] 只读账号与表白名单的可配置化
- [ ] 多轮追问