# DataTalk 评测报告

- 模型：`studymate-qwen`
- 语义校验：开启　自修复上限：2
- 题量：102　总耗时：80.6s

## 总体

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 执行准确率（strict） | **80.4%** | 结果集逐值相等 |
| 执行准确率（relaxed） | 80.4% | 容忍列顺序不同 |
| 首次生成准确率 | 64.7% | 一次生成即正确，无需修复 |
| 自修复救回 | 16 题 | 修复后才对 |
| 平均修复轮次 | 0.28 | 含 0 次的题 |
| 平均延迟 / P95 | 789ms / 2007ms | 端到端 |

## 分类

| 类别 | 题数 | strict | relaxed |
| --- | --- | --- | --- |
| 薪资 | 21 | 86% | 86% |
| 组合 | 21 | 71% | 71% |
| 计数 | 20 | 100% | 100% |
| 分组 | 20 | 70% | 70% |
| 技能 | 20 | 75% | 75% |

失败类型：col_count 2 题，values 10 题，empty 3 题，row_count 5 题

## 失败样例（最多 12 条）

### 30. 硕士和本科的平均日薪分别是多少？
- 类型：`col_count`　行数 gold/got：2/2　尝试：1
- 金标准：`select education, round(avg(salary_avg),1) from jobs where education in ('硕士','本科') and salary_avg is not null group by education order by education`
- 模型：`SELECT AVG(j.salary_avg) AS 平均日薪
FROM jobs j
JOIN (
    SELECT company_id, education
    FROM jobs
    WHERE education IN ('硕士', '本科')
    GROUP BY company_id, education
) sub
ON j.company_id = sub.company_id AND j.education = sub.education
WHERE j.salary_avg IS NOT NULL
GROUP BY j.education
ORDER B`

### 31. 要求每周5天的岗位平均日薪是多少？
- 类型：`values`　行数 gold/got：1/1　尝试：0
- 金标准：`select round(avg(salary_avg),1) from jobs where days_per_week=5 and salary_avg is not null`
- 模型：`SELECT AVG(days_per_week) AS 平均日薪
FROM jobs
WHERE days_per_week = 5`

### 40. 有薪资的岗位里日薪中位数是多少？
- 类型：`values`　行数 gold/got：1/1　尝试：0
- 金标准：`select round(avg(x),1) from (select salary_avg as x from jobs where salary_avg is not null order by x limit (select case when count(*)%2=1 then 1 else 2 end from jobs where salary_avg is not null) offset (select (count(*)-1)/2 from jobs where salary_avg is not null))`
- 模型：`SELECT ROUND(AVG(x), 1) AS 日薪中位数
FROM (SELECT salary_avg AS x FROM jobs WHERE salary_avg IS NOT NULL ORDER BY x
      LIMIT 1 OFFSET 0)`

### 49. 按行业统计平均日薪
- 类型：`empty`　行数 gold/got：4/0　尝试：1
- 金标准：`select c.industry, round(avg(j.salary_avg),1) as s from jobs j join companies c on c.id=j.company_id where j.salary_avg is not null group by c.industry order by s desc`
- 模型：`SELECT jobs.industry AS 行业, ROUND(AVG(jobs.salary_avg), 1) AS 平均日薪
FROM jobs
WHERE salary_avg IS NOT NULL
GROUP BY jobs.industry
ORDER BY 平均日薪 DESC
LIMIT 10`
- 错误：自修复失败：模型未能修正 SQL

### 50. 每周实习天数各有多少个岗位
- 类型：`row_count`　行数 gold/got：7/1　尝试：0
- 金标准：`select days_per_week, count(*) as n from jobs where days_per_week is not null group by days_per_week order by days_per_week`
- 模型：`SELECT AVG(days_per_week) AS 每周天数 FROM jobs WHERE days_per_week IS NOT NULL`

### 51. 实习月数分布，最多的5种
- 类型：`values`　行数 gold/got：5/5　尝试：0
- 金标准：`select months, count(*) as n from jobs where months is not null group by months order by n desc limit 5`
- 模型：`SELECT months AS 实习月数, COUNT(*) AS 岗位数
FROM jobs
WHERE salary_avg IS NOT NULL
GROUP BY months
ORDER BY 岗位数 DESC
LIMIT 5`

### 54. 哪个城市的岗位数量最多？
- 类型：`row_count`　行数 gold/got：1/42　尝试：0
- 金标准：`select city, count(*) as n from jobs where city is not null group by city order by n desc limit 1`
- 模型：`SELECT city AS 城市, COUNT(*) AS 岗位数 FROM jobs WHERE city IS NOT NULL GROUP BY city ORDER BY 岗位数 DESC LIMIT 50`

### 58. 平均日薪超过250元的城市有哪些？
- 类型：`empty`　行数 gold/got：4/0　尝试：3
- 金标准：`select city, round(avg(salary_avg),1) as s from jobs where city is not null and salary_avg is not null group by city having s>250 order by s desc`
- 模型：`SELECT jobs.city AS 城市, ROUND(AVG(jobs.salary_avg), 1) AS 平均日薪
FROM jobs
WHERE salary_avg IS NOT NULL
GROUP BY jobs.city
HAVING ROUND(AVG(jobs.salary_avg), 1) > 250
ORDER BY 平均日薪 DESC
LIMIT 50`
- 错误：执行失败且自修复次数用尽：语义校验未通过：按城市统计时请加 WHERE city IS NOT NULL，避免出现空城市分组

### 61. 深圳和北京哪个岗位多？
- 类型：`row_count`　行数 gold/got：2/1　尝试：0
- 金标准：`select city, count(*) as n from jobs where city in ('北京','深圳') group by city order by n desc`
- 模型：`SELECT city AS 城市, COUNT(*) AS 岗位数
FROM jobs WHERE salary_avg IS NOT NULL AND (city = '深圳' OR city = '北京')
GROUP BY city
ORDER BY 岗位数 DESC
LIMIT 1`

### 66. 要求大模型/LLM 的岗位有多少个？
- 类型：`values`　行数 gold/got：1/1　尝试：2
- 金标准：`select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='大模型/LLM'`
- 模型：`SELECT COUNT(*) AS 岗位数
FROM jobs
JOIN job_skills js ON js.job_id = jobs.id
JOIN skills s ON s.id = js.skill_id
WHERE s.name IN ('大模型/LLM', 'LangChain')
GROUP BY jobs.id
HAVING COUNT(DISTINCT s.name) = 2
ORDER BY jobs.id DESC
LIMIT 1`

### 71. 北京要求 Python 的岗位有多少个？
- 类型：`values`　行数 gold/got：1/1　尝试：1
- 金标准：`select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='Python' and j.city='北京'`
- 模型：`SELECT COUNT(DISTINCT jobs.id) AS 岗位数
FROM jobs
JOIN job_skills ON jobs.id = job_skills.job_id
JOIN skills ON job_skills.skill_id = skills.id
WHERE jobs.city = '北京' AND skills.name = 'Python' AND jobs.salary_avg IS NOT NULL
LIMIT 50`

### 72. 上海要求大模型/LLM 的岗位有多少个？
- 类型：`values`　行数 gold/got：1/1　尝试：1
- 金标准：`select count(distinct j.id) from jobs j join job_skills js on js.job_id=j.id join skills s on s.id=js.skill_id where s.name='大模型/LLM' and j.city='上海'`
- 模型：`SELECT COUNT(DISTINCT jobs.id) AS 岗位数
FROM jobs
JOIN job_skills ON jobs.id = job_skills.job_id
JOIN skills ON job_skills.skill_id = skills.id
WHERE jobs.city = '上海' AND skills.name IN ('大模型/LLM', 'RAG', 'Agent', 'Prompt', '微调', 'LangChain')`

