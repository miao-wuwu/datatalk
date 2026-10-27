"""从爬取到的实习岗位 JSON 构建演示数据库 data/jobs.db。

数据来源：
  D:\\工作区\\_scrape\\out\\sxs_jobs.json      （实习僧，1604 条）
  D:\\工作区\\_scrape\\out\\nowcoder_jobs.json  （牛客，436 条）

用法：
  python backend/scripts/seed_db.py
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # D:\datatalk
DATA = ROOT / "data"
OUT_DB = DATA / "jobs.db"

SXS = Path(r"D:\工作区\_scrape\out\sxs_jobs.json")
NOWCODER = Path(r"D:\工作区\_scrape\out\nowcoder_jobs.json")

SCHEMA = """
CREATE TABLE companies (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    city     TEXT,
    industry TEXT,
    job_count INTEGER DEFAULT 0
);

CREATE TABLE jobs (
    id            INTEGER PRIMARY KEY,
    company_id    INTEGER NOT NULL REFERENCES companies(id),
    title         TEXT NOT NULL,
    city          TEXT,
    salary_min    REAL,
    salary_max    REAL,
    salary_avg    REAL,
    education     TEXT,
    days_per_week INTEGER,
    months        INTEGER,
    source        TEXT,
    publish_date  TEXT,
    url           TEXT,
    jd_text       TEXT
);

CREATE TABLE skills (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    category TEXT
);

CREATE TABLE job_skills (
    job_id   INTEGER NOT NULL REFERENCES jobs(id),
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX idx_jobs_city ON jobs(city);
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_salary ON jobs(salary_avg);
CREATE INDEX idx_job_skills_skill ON job_skills(skill_id);
"""

# ---------------------------------------------------------------- 技能词表
# (名称, 类别, 正则)
SKILLS = [
    ("React", "前端", r"\breact\b|react\.?js|reactjs"),
    ("Vue", "前端", r"\bvue\b|vue\.?js|vue3|vue2|vuex|pinia"),
    ("Angular", "前端", r"\bangular\b"),
    ("TypeScript", "前端", r"typescript|\bts\b"),
    ("JavaScript", "前端", r"javascript|\bjs\b|es6"),
    ("HTML/CSS", "前端", r"html5?|\bcss3?\b|sass|less"),
    ("小程序", "前端", r"小程序|uni-?app|taro|flutter"),
    ("Node.js", "前端", r"node\.?js|nodejs|\bnode\b"),
    ("Python", "后端", r"\bpython\b|django|flask|fastapi"),
    ("Java", "后端", r"\bjava\b|springboot|spring boot|springmvc|\bjvm\b"),
    ("Go", "后端", r"\bgolang\b|\bgo\b语言"),
    ("C++", "后端", r"c\+\+|c/c\+\+"),
    ("Rust", "后端", r"\brust\b"),
    ("SQL", "数据", r"\bsql\b|mysql|postgres|oracle|hive|clickhouse"),
    ("MySQL", "数据", r"mysql"),
    ("Redis", "后端", r"\bredis\b"),
    ("MongoDB", "后端", r"mongo"),
    ("Kafka", "后端", r"kafka|消息队列|rabbitmq"),
    ("Docker", "工程", r"docker|k8s|kubernetes|容器化"),
    ("Linux", "工程", r"\blinux\b|shell|ubuntu|centos"),
    ("Git", "工程", r"\bgit\b|github|gitlab"),
    ("CI/CD", "工程", r"ci/cd|jenkins|持续集成|流水线"),
    ("PyTorch", "AI", r"pytorch|\btorch\b"),
    ("TensorFlow", "AI", r"tensorflow|\btf\b"),
    ("机器学习", "AI", r"机器学习|machine learning|xgboost|lightgbm"),
    ("深度学习", "AI", r"深度学习|神经网络|transformer|cnn|rnn"),
    ("大模型/LLM", "AI", r"大模型|llm|gpt|deepseek|qwen|通义"),
    ("RAG", "AI", r"\brag\b|检索增强|向量检索|向量数据库|embedding"),
    ("Agent", "AI", r"\bagent\b|智能体|multi-?agent|tool use|工具调用"),
    ("Prompt", "AI", r"prompt|提示词"),
    ("LangChain", "AI", r"langchain|llamaindex|dify|coze"),
    ("微调", "AI", r"微调|fine-?tun|sft|lora|rlhf"),
    ("数据分析", "数据", r"数据分析|数据挖掘|数据清洗|指标|报表|bi\b"),
    ("爬虫", "数据", r"爬虫|scrapy|selenium|数据采集"),
    ("算法", "算法", r"算法|数据结构|leetcode|acm"),
    ("测试", "测试", r"测试|自动化测试|pytest|selenium|jmeter"),
    ("嵌入式", "硬件", r"嵌入式|单片机|\bmcu\b|stm32|rtos|fpga"),
    ("运维/部署", "工程", r"运维|部署|nginx|负载均衡|监控"),
]

industries = {
    "字节跳动": "互联网", "抖音": "互联网", "腾讯": "互联网", "阿里巴巴": "互联网",
    "阿里": "互联网", "百度": "互联网", "美团": "互联网", "京东": "互联网",
    "快手": "互联网", "小红书": "互联网", "哔哩哔哩": "互联网", "B站": "互联网",
    "滴滴": "互联网", "网易": "互联网", "小米": "硬件", "华为": "硬件",
    "蔚来": "汽车", "理想": "汽车", "小鹏": "汽车", "比亚迪": "汽车",
    "博世": "汽车", "特斯拉": "汽车", "商汤": "AI", "旷视": "AI",
    "智谱": "AI", "月之暗面": "AI", "MiniMax": "AI", "出门问问": "AI",
    "中国平安": "金融", "招商银行": "金融", "蚂蚁": "金融", "京东科技": "金融",
    "新东方": "教育", "好未来": "教育", "猿辅导": "教育", "作业帮": "教育",
}


CITY_BAD = {"全国", "可转正", "提供转正机会", "面议", "远程", "不限"}
EDU_MAP = {"硕士及以上": "硕士", "本科及以上": "本科", "大专及以上": "大专", "博士及以上": "博士"}


def clean_city(text: str) -> str | None:
    """爬来的城市字段有噪音：多城市拼接、把「可转正」写进城市……清洗掉。"""
    c = (text or "").strip()
    if not c:
        return None
    if "," in c or "，" in c:
        c = re.split(r"[,，]", c)[0].strip()
    if c in CITY_BAD or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", c):
        return None
    return c


def clean_edu(text: str) -> str:
    e = (text or "").strip() or "不限"
    return EDU_MAP.get(e, e)


def parse_salary(text: str) -> tuple[float | None, float | None, float | None]:
    """把 '200-300/天'、'300/天'、'3000-4000/月'、'薪资面议' 转成 (min, max, avg)。"""
    if not text:
        return None, None, None
    t = text.replace(" ", "").replace("～", "-").replace("~", "-")
    rng = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", t)
    single = re.search(r"(\d+(?:\.\d+)?)", t)
    unit_month = "/月" in t or "元/月" in t
    lo = hi = None
    if rng:
        lo, hi = float(rng.group(1)), float(rng.group(2))
    elif single and ("/天" in t or "/月" in t):
        lo = hi = float(single.group(1))
    if lo is None:
        return None, None, None
    if unit_month:
        lo, hi = lo / 21.75, hi / 21.75
    return lo, hi, round((lo + hi) / 2, 1)


def pick(obj: dict, *names: str) -> str:
    for n in names:
        v = obj.get(n)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def to_int(text: str) -> int | None:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()

    raw: list[dict] = []
    for path, source in ((SXS, "实习僧"), (NOWCODER, "牛客")):
        items = json.loads(path.read_text(encoding="utf-8"))
        for it in items:
            raw.append({**it, "_source": source})
    print(f"读入 {len(raw)} 条原始岗位")

    # 按 (公司, 标题) 去重，实习僧优先
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for it in raw:
        company = pick(it, "company", "compName")
        title = pick(it, "title", "jobName", "jobTitle")
        if not company or not title:
            continue
        key = (company, title)
        if key in seen:
            continue
        seen.add(key)
        lo, hi, avg = parse_salary(pick(it, "salary", "monthSalary", "salaryDesc"))
        if avg is not None and not (40 <= avg <= 2000):   # 明显解析噪声（月薪单位错、面议残留）
            lo = hi = avg = None
        rows.append({
            "company": company,
            "title": title,
            "city": clean_city(pick(it, "city", "jobCity", "dq")),
            "salary_min": lo,
            "salary_max": hi,
            "salary_avg": avg,
            "education": clean_edu(pick(it, "edu", "requireEduLevel", "jobDegree")),
            "days_per_week": to_int(pick(it, "days_week", "durationDays")),
            "months": to_int(pick(it, "months", "durationMonths")),
            "source": it["_source"],
            "publish_date": pick(it, "publish", "refresh", "refreshTime")[:10] or None,
            "url": pick(it, "url", "link"),
            "jd_text": (pick(it, "jd", "jd_text") or pick(it, "requirements", "duties"))[:4000],
        })
    print(f"去重后 {len(rows)} 条岗位")

    # 公司 -> 城市/岗位数
    city_by_company: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r["city"]:
            city_by_company[r["company"]][r["city"]] += 1

    names = sorted({r["company"] for r in rows})
    companies = []
    for i, name in enumerate(names, 1):
        top = city_by_company[name].most_common(1)
        city = top[0][0] if top else None
        industry = next((v for k, v in industries.items() if k in name), "其他")
        companies.append((i, name, city, industry, sum(city_by_company[name].values())))
    company_id = {c[1]: c[0] for c in companies}

    compiled = [(n, cat, re.compile(p, re.I)) for n, cat, p in SKILLS]
    skill_name = [s[0] for s in compiled]
    skill_id = {n: i for i, n in enumerate(skill_name, 1)}

    jobs, links = [], []
    for i, r in enumerate(rows, 1):
        jobs.append((
            i, company_id[r["company"]], r["title"], r["city"],
            r["salary_min"], r["salary_max"], r["salary_avg"],
            r["education"], r["days_per_week"], r["months"],
            r["source"], r["publish_date"], r["url"], r["jd_text"],
        ))
        text = f'{r["title"]} {r["jd_text"]}'
        for name, _cat, rx in compiled:
            if rx.search(text):
                links.append((i, skill_id[name]))

    con = sqlite3.connect(OUT_DB)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO companies VALUES (?,?,?,?,?)", companies)
        con.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", jobs)
        con.executemany(
            "INSERT INTO skills VALUES (?,?,?)",
            [(skill_id[n], n, cat) for n, cat, _ in compiled],
        )
        con.executemany("INSERT INTO job_skills VALUES (?,?)", links)
        con.commit()
    finally:
        con.close()

    size = OUT_DB.stat().st_size
    print(f"写入 {OUT_DB}（{size/1024:.0f} KB）")
    print(f"  公司 {len(companies)}  岗位 {len(jobs)}  技能 {len(skill_name)}  关联 {len(links)}")
    print("  城市 Top5:", Counter(r["city"] for r in rows).most_common(5))
    print("  有薪资的岗位:", sum(1 for r in rows if r["salary_avg"]), "条")


if __name__ == "__main__":
    main()