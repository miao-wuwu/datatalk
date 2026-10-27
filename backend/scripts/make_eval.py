"""构建 100 题金标准评测集：问题 + 金标准 SQL，并执行 SQL 落盘结果集。

用法： python -m scripts.make_eval      （在 backend 目录，或设置 PYTHONPATH）
产物： data/eval_set.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "jobs.db"
OUT = ROOT / "data" / "eval_set.json"

# (类别, 问题, 金标准 SQL, 是否对顺序敏感)
CASES: list[tuple[str, str, str, bool]] = [
    # ---------- A. 计数与筛选 ----------
    ("计数", "北京有多少个实习岗位？", "select count(*) from jobs where city='北京'", False),
    ("计数", "上海有多少个实习岗位？", "select count(*) from jobs where city='上海'", False),
    ("计数", "深圳有多少个实习岗位？", "select count(*) from jobs where city='深圳'", False),
    ("计数", "杭州有多少个实习岗位？", "select count(*) from jobs where city='杭州'", False),
    ("计数", "广州有多少个实习岗位？", "select count(*) from jobs where city='广州'", False),
    ("计数", "成都一共有多少个岗位？", "select count(*) from jobs where city='成都'", False),
    ("计数", "南京有多少个岗位？", "select count(*) from jobs where city='南京'", False),
    ("计数", "苏州有多少个岗位？", "select count(*) from jobs where city='苏州'", False),
    ("计数", "要求硕士学历的岗位有多少个？", "select count(*) from jobs where education='硕士'", False),
    ("计数", "要求博士学历的岗位有多少个？", "select count(*) from jobs where education='博士'", False),
    ("计数", "学历不限的岗位有多少个？", "select count(*) from jobs where education='不限'", False),
    ("计数", "大专学历的岗位有多少个？", "select count(*) from jobs where education='大专'", False),
    ("计数", "有多少家不同的公司在招实习？", "select count(distinct company_id) from jobs", False),
    ("计数", "有多少个岗位标注了薪资？", "select count(*) from jobs where salary_avg is not null", False),
    ("计数", "有多少个岗位没有标注薪资？", "select count(*) from jobs where salary_avg is null", False),
    ("计数", "来自实习僧的岗位有多少个？", "select count(*) from jobs where source='实习僧'", False),
    ("计数", "来自牛客的岗位有多少个？", "select count(*) from jobs where source='牛客'", False),
    ("计数", "要求每周实习5天的岗位有多少个？", "select count(*) from jobs where days_per_week=5", False),
    ("计数", "实习期为3个月的岗位有多少个？", "select count(*) from jobs where months=3", False),
    ("计数", "岗位覆盖了多少个城市？", "select count(distinct city) from jobs where city is not null", False),
    # ---------- B. 薪资统计 ----------
    ("薪资", "所有岗位的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where salary_avg is not null", False),
    ("薪资", "最高的日薪是多少？", "select max(salary_avg) from jobs where salary_avg is not null", False),
    ("薪资", "最低的日薪是多少？", "select min(salary_avg) from jobs where salary_avg is not null", False),
    ("薪资", "北京岗位的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where city='北京' and salary_avg is not null", False),
    ("薪资", "上海岗位的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where city='上海' and salary_avg is not null", False),
    ("薪资", "深圳岗位的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where city='深圳' and salary_avg is not null", False),
    ("薪资", "杭州岗位的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where city='杭州' and salary_avg is not null", False),
    ("薪资", "要求硕士的岗位平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where education='硕士' and salary_avg is not null", False),
    ("薪资", "要求本科的岗位平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where education='本科' and salary_avg is not null", False),
    ("薪资", "硕士和本科的平均日薪分别是多少？", "select education, round(avg(salary_avg),1) from jobs where education in ('硕士','本科') and salary_avg is not null group by education order by education", True),
    ("薪资", "要求每周5天的岗位平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where days_per_week=5 and salary_avg is not null", False),
    ("薪资", "互联网行业的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs j join companies c on c.id=j.company_id where c.industry='互联网' and salary_avg is not null", False),
    ("薪资", "汽车行业的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs j join companies c on c.id=j.company_id where c.industry='汽车' and salary_avg is not null", False),
    ("薪资", "金融行业的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs j join companies c on c.id=j.company_id where c.industry='金融' and salary_avg is not null", False),
    ("薪资", "硬件行业的平均日薪是多少？", "select round(avg(salary_avg),1) from jobs j join companies c on c.id=j.company_id where c.industry='硬件' and salary_avg is not null", False),
    ("薪资", "日薪超过300元的岗位有多少个？", "select count(*) from jobs where salary_avg>300", False),
    ("薪资", "日薪低于150元的岗位有多少个？", "select count(*) from jobs where salary_avg<150", False),
    ("薪资", "北京日薪最高的岗位是多少钱？", "select max(salary_avg) from jobs where city='北京' and salary_avg is not null", False),
    ("薪资", "上海日薪最高的5个岗位是哪几个？", "select title, salary_avg from jobs where city='上海' and salary_avg is not null order by salary_avg desc limit 5", True),
    ("薪资", "有薪资的岗位里日薪中位数是多少？", "select round(avg(x),1) from (select salary_avg as x from jobs where salary_avg is not null order by x limit (select case when count(*)%2=1 then 1 else 2 end from jobs where salary_avg is not null) offset (select (count(*)-1)/2 from jobs where salary_avg is not null))", False),
    ("薪资", "平均日薪最高的城市是哪个？", "select city, round(avg(salary_avg),1) as s from jobs where city is not null and salary_avg is not null group by city order by s desc limit 1", True),
    # ---------- C. 分组与排序 ----------
    ("分组", "各城市的岗位数量排名前十", "select city, count(*) as n from jobs where city is not null group by city order by n desc limit 10", True),
    ("分组", "各城市平均日薪从高到低前十个", "select city, round(avg(salary_avg),1) as s from jobs where city is not null and salary_avg is not null group by city order by s desc limit 10", True),
    ("分组", "招聘岗位数量最多的5家公司", "select c.name, count(*) as n from jobs j join companies c on c.id=j.company_id group by c.id order by n desc limit 5", True),
    ("分组", "平均日薪最高的5家公司", "select c.name, round(avg(j.salary_avg),1) as s from jobs j join companies c on c.id=j.company_id where j.salary_avg is not null group by c.id order by s desc limit 5", True),
    ("分组", "不同学历的岗位数量分布", "select education, count(*) as n from jobs where education is not null group by education order by n desc", True),
    ("分组", "不同学历的平均日薪", "select education, round(avg(salary_avg),1) as s from jobs where education is not null and salary_avg is not null group by education order by s desc", True),
    ("分组", "按行业统计岗位数量", "select c.industry, count(*) as n from jobs j join companies c on c.id=j.company_id group by c.industry order by n desc", True),
    ("分组", "按行业统计平均日薪", "select c.industry, round(avg(j.salary_avg),1) as s from jobs j join companies c on c.id=j.company_id where j.salary_avg is not null group by c.industry order by s desc", True),
    ("分组", "每周实习天数各有多少个岗位", "select days_per_week, count(*) as n from jobs where days_per_week is not null group by days_per_week order by days_per_week", True),
    ("分组", "实习月数分布，最多的5种", "select months, count(*) as n from jobs where months is not null group by months order by n desc limit 5", True),
    ("分组", "北京招聘岗位最多的5家公司", "select c.name, count(*) as n from jobs j join companies c on c.id=j.company_id where j.city='北京' group by c.id order by n desc limit 5", True),
    ("分组", "上海平均日薪最高的5家公司", "select c.name, round(avg(j.salary_avg),1) as s from jobs j join companies c on c.id=j.company_id where j.city='上海' and j.salary_avg is not null group by c.id order by s desc limit 5", True),
    ("分组", "哪个城市的岗位数量最多？", "select city, count(*) as n from jobs where city is not null group by city order by n desc limit 1", True),
    ("分组", "哪个行业的岗位数量最多？", "select c.industry, count(*) as n from jobs j join companies c on c.id=j.company_id group by c.industry order by n desc limit 1", True),
    ("分组", "哪个学历要求的岗位最多？", "select education, count(*) as n from jobs where education is not null group by education order by n desc limit 1", True),
    ("分组", "岗位数超过20个的城市有哪些？", "select city, count(*) as n from jobs where city is not null group by city having n>20 order by n desc", True),
    ("分组", "平均日薪超过250元的城市有哪些？", "select city, round(avg(salary_avg),1) as s from jobs where city is not null and salary_avg is not null group by city having s>250 order by s desc", True),
    ("分组", "各来源的岗位数量", "select source, count(*) as n from jobs group by source order by n desc", True),
    ("分组", "各来源的平均日薪", "select source, round(avg(salary_avg),1) as s from jobs where salary_avg is not null group by source order by s desc", True),
    ("分组", "深圳和北京哪个岗位多？", "select city, count(*) as n from jobs where city in ('北京','深圳') group by city order by n desc", True),
    # ---------- D. 技能（多表连表） ----------
    ("技能", "要求 Python 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python'", False),
    ("技能", "要求 Agent 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Agent'", False),
    ("技能", "要求算法的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='算法'", False),
    ("技能", "要求 RAG 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='RAG'", False),
    ("技能", "要求大模型/LLM 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='大模型/LLM'", False),
    ("技能", "要求 React 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='React'", False),
    ("技能", "要求 Python 的岗位平均日薪是多少？", "select round(avg(j.salary_avg),1) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and j.salary_avg is not null", False),
    ("技能", "要求 Agent 的岗位平均日薪是多少？", "select round(avg(j.salary_avg),1) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Agent' and j.salary_avg is not null", False),
    ("技能", "招 Python 最多的5家公司", "select c.name, count(distinct j.id) as n from jobs j join companies c on c.id=j.company_id join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' group by c.id order by n desc limit 5", True),
    ("技能", "北京要求 Python 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and j.city='北京'", False),
    ("技能", "上海要求大模型/LLM 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='大模型/LLM' and j.city='上海'", False),
    ("技能", "同时要求 Python 和 Agent 的岗位有多少个？", "select count(*) from (select js.job_id from job_skills js join skills s on s.id=js.skill_id where s.name in ('Python','Agent') group by js.job_id having count(distinct s.name)=2)", False),
    ("技能", "要求 SQL 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='SQL'", False),
    ("技能", "要求 MySQL 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='MySQL'", False),
    ("技能", "要求深度学习的岗位平均日薪是多少？", "select round(avg(j.salary_avg),1) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='深度学习' and j.salary_avg is not null", False),
    ("技能", "技能数量最多的5个岗位是哪些？", "select j.title, count(*) as n from jobs j join job_skills js on js.job_id=j.id group by j.id order by n desc limit 5", True),
    ("技能", "每个技能类别下有多少个岗位？", "select s.category, count(distinct js.job_id) as n from skills s join job_skills js on js.skill_id=s.id group by s.category order by n desc", True),
    ("技能", "要求 Java 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Java'", False),
    ("技能", "要求 C++ 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='C++'", False),
    ("技能", "要求 PyTorch 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='PyTorch'", False),
    # ---------- E. 组合条件与陷阱 ----------
    ("组合", "北京招 Python 的公司有多少家？", "select count(distinct j.company_id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and j.city='北京'", False),
    ("组合", "上海要求硕士学历的岗位有多少个？", "select count(*) from jobs where city='上海' and education='硕士'", False),
    ("组合", "深圳要求本科、日薪超过200的岗位有多少个？", "select count(*) from jobs where city='深圳' and education='本科' and salary_avg>200", False),
    ("组合", "北京互联网行业有哪些公司在招人？", "select distinct c.name from jobs j join companies c on c.id=j.company_id where j.city='北京' and c.industry='互联网' order by c.name", True),
    ("组合", "杭州要求每周4天及以上的岗位有多少个？", "select count(*) from jobs where city='杭州' and days_per_week>=4", False),
    ("组合", "广州要求实习3个月及以上的岗位有多少个？", "select count(*) from jobs where city='广州' and months>=3", False),
    ("组合", "北京招 Agent 但没写薪资的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Agent' and j.city='北京' and j.salary_avg is null", False),
    ("组合", "北京和上海的平均日薪分别是多少？", "select city, round(avg(salary_avg),1) from jobs where city in ('北京','上海') and salary_avg is not null group by city order by city", True),
    ("组合", "要求本科且招 Python 的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and j.education='本科'", False),
    ("组合", "要求硕士且招算法技能的岗位有多少个？", "select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='算法' and j.education='硕士'", False),
    ("组合", "平均每家公司招几个岗位？", "select round(avg(job_count),1) from companies where job_count>0", False),
    ("组合", "公司数量最多的5个城市", "select city, count(*) as n from companies where city is not null group by city order by n desc limit 5", True),
    ("组合", "岗位数最少但至少有5个岗位的城市是哪个？", "select city, count(*) as n from jobs where city is not null group by city having n>=5 order by n asc limit 1", True),
    ("组合", "每周5天且日薪超过300的岗位有多少个？", "select count(*) from jobs where days_per_week=5 and salary_avg>300", False),
    ("组合", "互联网行业招 Python 的岗位有多少个？", "select count(distinct j.id) from jobs j join companies c on c.id=j.company_id join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and c.industry='互联网'", False),
    ("组合", "汽车行业招人最多的公司是哪家？", "select c.name, count(*) as n from jobs j join companies c on c.id=j.company_id where c.industry='汽车' group by c.id order by n desc limit 1", True),
    ("组合", "硕士学历岗位的平均日薪比本科高多少元？", "select round((select avg(salary_avg) from jobs where education='硕士' and salary_avg is not null) - (select avg(salary_avg) from jobs where education='本科' and salary_avg is not null),1)", False),
    ("组合", "同时要求 Python 和机器学习的岗位有多少个？", "select count(*) from (select js.job_id from job_skills js join skills s on s.id=js.skill_id where s.name in ('Python','机器学习') group by js.job_id having count(distinct s.name)=2)", False),
    ("组合", "北京一共有多少家公司在招聘？", "select count(distinct company_id) from jobs where city='北京'", False),
    ("组合", "实习6个月的岗位平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where months=6 and salary_avg is not null", False),
    ("组合", "不限学历的岗位平均日薪是多少？", "select round(avg(salary_avg),1) from jobs where education='不限' and salary_avg is not null", False),
]


def main() -> int:
    if not DB.exists():
        print(f"缺少数据库：{DB}")
        return 1
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    items, bad = [], 0
    for idx, (cat, q, sql, ordered) in enumerate(CASES, 1):
        try:
            cur = con.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [[r for r in row] for row in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}] SQL 失败: {exc}\n    {sql}")
            bad += 1
            continue
        if not rows:
            print(f"[{idx}] 结果为空: {q}")
            bad += 1
            continue
        items.append({
            "id": idx, "category": cat, "question": q, "sql": sql,
            "ordered": ordered, "columns": cols, "rows": rows,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {OUT}：{len(items)} 题（跳过 {bad}）")
    from collections import Counter
    print("类别：", dict(Counter(i["category"] for i in items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())