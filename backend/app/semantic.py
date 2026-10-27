"""语义层：指标口径、同义词、few-shot 示例检索。

为什么需要语义层：
  「平均日薪」到底算 salary_avg 的均值，还是 (min+max)/2 的均值？「岗位数」要不要去重？
  这类口径不能让模型每次自己发挥，必须写死在配置里，跟 schema 一起注进 prompt。
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- 指标口径
METRICS = [
    {
        "name": "岗位数",
        "sql": "COUNT(DISTINCT jobs.id)",
        "desc": "去重后的岗位条数；按公司统计时用 COUNT(DISTINCT jobs.id)",
    },
    {
        "name": "平均日薪",
        "sql": "ROUND(AVG(jobs.salary_avg), 1)",
        "desc": "salary_avg = (salary_min + salary_max)/2，单位元/天；必须先过滤 salary_avg IS NOT NULL",
    },
    {
        "name": "最高/最低日薪",
        "sql": "MAX(jobs.salary_max) / MIN(jobs.salary_min)",
        "desc": "同样只看 salary_avg IS NOT NULL 的岗位",
    },
    {
        "name": "每周天数",
        "sql": "AVG(jobs.days_per_week)",
        "desc": "days_per_week 为整数，1~7；缺失为 NULL",
    },
    {
        "name": "技能覆盖岗位数",
        "sql": "COUNT(DISTINCT job_skills.job_id)",
        "desc": "通过 job_skills 关联到 skills.name 后统计",
    },
]

# ---------------------------------------------------------------- 同义词
SYNONYMS = {
    "日薪": "salary_avg（元/天）",
    "薪资": "salary_avg / salary_min / salary_max",
    "工资": "salary_avg",
    "学历": "jobs.education（本科/硕士/大专/博士/不限）",
    "城市": "jobs.city 或 companies.city",
    "公司": "companies.name",
    "岗位": "jobs.title",
    "技能": "skills.name",
    "方向": "skills.category（前端/后端/AI/数据/工程/算法/测试/硬件）",
    "大模型": "skills.name IN ('大模型/LLM','RAG','Agent','Prompt','微调','LangChain')",
    "AI": "skills.category = 'AI'",
    "前端": "skills.category = '前端'",
    "后端": "skills.category = '后端'",
    "实习生": "全部岗位都是实习，无需额外过滤",
}

# ---------------------------------------------------------------- few-shot
# (问题, SQL, 关键词)——问题里出现的关键词用于检索最相关的示例
EXAMPLES: list[tuple[str, str, list[str]]] = [
    (
        "北京有哪些公司在招 Python 实习生？",
        """SELECT c.name AS 公司, COUNT(*) AS 岗位数
FROM jobs j JOIN companies c ON c.id = j.company_id
JOIN job_skills js ON js.job_id = j.id
JOIN skills s ON s.id = js.skill_id
WHERE j.city = '北京' AND s.name = 'Python'
GROUP BY c.name ORDER BY 岗位数 DESC LIMIT 20""",
        ["北京", "公司", "Python"],
    ),
    (
        "上海实习生的平均日薪是多少？",
        """SELECT ROUND(AVG(salary_avg), 1) AS 平均日薪
FROM jobs WHERE city = '上海' AND salary_avg IS NOT NULL""",
        ["上海", "平均", "日薪"],
    ),
    (
        "不同城市的岗位数量排名",
        """SELECT city AS 城市, COUNT(*) AS 岗位数
FROM jobs GROUP BY city ORDER BY 岗位数 DESC LIMIT 20""",
        ["城市", "数量", "排名"],
    ),
    (
        "招大模型相关岗位最多的 10 家公司",
        """SELECT c.name AS 公司, COUNT(DISTINCT j.id) AS 岗位数
FROM skills s
JOIN job_skills js ON js.skill_id = s.id
JOIN jobs j ON j.id = js.job_id
JOIN companies c ON c.id = j.company_id
WHERE s.name IN ('大模型/LLM','RAG','Agent','Prompt','微调','LangChain')
GROUP BY c.name ORDER BY 岗位数 DESC LIMIT 10""",
        ["大模型", "公司", "最多"],
    ),
    (
        "本科岗位和硕士岗位的平均薪资对比",
        """SELECT education AS 学历, ROUND(AVG(salary_avg), 1) AS 平均日薪, COUNT(*) AS 岗位数
FROM jobs WHERE salary_avg IS NOT NULL AND education IN ('本科','硕士')
GROUP BY education""",
        ["本科", "硕士", "对比", "薪资"],
    ),
    (
        "要求 React 的岗位，城市分布是怎样的？",
        """SELECT j.city AS 城市, COUNT(*) AS 岗位数
FROM jobs j JOIN job_skills js ON js.job_id = j.id JOIN skills s ON s.id = js.skill_id
WHERE s.name = 'React' GROUP BY j.city ORDER BY 岗位数 DESC""",
        ["React", "城市", "分布"],
    ),
    (
        "哪些岗位同时要求 Python 和 大模型？",
        """SELECT DISTINCT j.title AS 岗位, c.name AS 公司, j.city AS 城市, j.salary_avg AS 日薪
FROM jobs j JOIN companies c ON c.id = j.company_id
WHERE j.id IN (SELECT js.job_id FROM job_skills js JOIN skills s ON s.id = js.skill_id WHERE s.name = 'Python')
  AND j.id IN (SELECT js.job_id FROM job_skills js JOIN skills s ON s.id = js.skill_id WHERE s.name = '大模型/LLM')
ORDER BY j.salary_avg DESC LIMIT 50""",
        ["同时", "Python", "大模型"],
    ),
    (
        "日薪超过 300 元的岗位有多少个？",
        """SELECT COUNT(*) AS 岗位数 FROM jobs WHERE salary_avg > 300""",
        ["超过", "日薪", "多少"],
    ),
    (
        "前端岗位的薪资中位数大概多少？",
        """SELECT ROUND(AVG(salary_avg), 1) AS 平均日薪, MIN(salary_min) AS 最低, MAX(salary_max) AS 最高, COUNT(*) AS 样本数
FROM jobs j JOIN job_skills js ON js.job_id = j.id JOIN skills s ON s.id = js.skill_id
WHERE s.category = '前端' AND j.salary_avg IS NOT NULL""",
        ["前端", "薪资", "中位"],
    ),
    (
        "每周要求 5 天的岗位占多少比例？",
        """SELECT ROUND(100.0 * SUM(CASE WHEN days_per_week = 5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS 占比百分比,
COUNT(*) AS 岗位总数
FROM jobs WHERE days_per_week IS NOT NULL""",
        ["每周", "5天", "比例"],
    ),
]

# 常见追问的兜底示例（检索不到时用）
FALLBACK_EXAMPLE = (
    "各城市的岗位数和平均日薪",
    """SELECT city AS 城市, COUNT(*) AS 岗位数, ROUND(AVG(salary_avg), 1) AS 平均日薪
FROM jobs WHERE salary_avg IS NOT NULL GROUP BY city ORDER BY 岗位数 DESC LIMIT 20""",
)


def glossary_text() -> str:
    from . import db

    metrics = "\n".join(f"- {m['name']}：{m['sql']}；{m['desc']}" for m in METRICS)
    syn = "\n".join(f"- {k} → {v}" for k, v in SYNONYMS.items())
    skills = db.skill_names()
    return (
        f"指标口径（必须遵守）：\n{metrics}\n\n"
        f"词汇映射：\n{syn}\n\n"
        f"skills.name 只能取这些值（共 {len(skills)} 个，逐字照抄）：\n"
        + "、".join(skills)
        + "\n（skills.category 取值：前端 / 后端 / AI / 数据 / 工程 / 算法 / 测试 / 硬件）"
    )


def _tokens(text: str) -> set[str]:
    words = set(re.findall(r"[A-Za-z][A-Za-z0-9.+#/-]+|[\u4e00-\u9fff]{2,4}", text))
    return {w.lower() for w in words}


def pick_examples(question: str, k: int = 3) -> list[tuple[str, str]]:
    """按关键词重合度挑 few-shot；一个都不沾时用兜底示例。"""
    q = _tokens(question)
    scored = []
    for nl, sql, keys in EXAMPLES:
        hit = sum(1 for key in keys if any(key.lower() in t or t in key.lower() for t in q))
        if hit:
            scored.append((hit, nl, sql))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return [FALLBACK_EXAMPLE]
    return [(nl, sql) for _, nl, sql in scored[:k]]