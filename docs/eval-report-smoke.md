# DataTalk 评测报告 · smoke

- 模型：`studymate-qwen`
- 语义校验：开启　自修复上限：2
- 题量：40　总耗时：20.9s

## 总体

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 执行准确率（strict） | **92.5%** | 结果集逐值相等 |
| 执行准确率（relaxed） | 92.5% | 容忍列顺序不同 |
| 首次生成准确率 | 90.0% | 一次生成即正确，无需修复 |
| 自修复救回 | 1 题 | 修复后才对 |
| 平均修复轮次 | 0.15 | 含 0 次的题 |
| 平均延迟 / P95 | 521ms / 1440ms | 端到端 |

## 分类

| 类别 | 题数 | strict | relaxed |
| --- | --- | --- | --- |
| 计数 | 20 | 100% | 100% |
| 薪资 | 20 | 85% | 85% |

失败类型：row_count 1 题，values 1 题，empty 1 题

## 失败样例（最多 12 条）

### 30. 硕士和本科的平均日薪分别是多少？
- 类型：`row_count`　行数 gold/got：2/1　尝试：1
- 金标准：`select education, round(avg(salary_avg),1) from jobs where education in ('硕士','本科') and salary_avg is not null group by education order by education`
- 模型：`SELECT
    education AS 学历,
    ROUND(AVG(salary_avg), 1) AS 平均日薪
FROM jobs
WHERE education IN ('硕士', '本科')
GROUP BY education
ORDER BY 平均日薪 DESC
LIMIT 1`

### 31. 要求每周5天的岗位平均日薪是多少？
- 类型：`values`　行数 gold/got：1/1　尝试：1
- 金标准：`select round(avg(salary_avg),1) from jobs where days_per_week=5 and salary_avg is not null`
- 模型：`SELECT AVG(days_per_week) AS 平均日薪
FROM jobs
WHERE days_per_week IS NOT NULL
GROUP BY days_per_week
HAVING days_per_week = 5
ORDER BY days_per_week DESC
LIMIT 1`

### 40. 有薪资的岗位里日薪中位数是多少？
- 类型：`empty`　行数 gold/got：1/0　尝试：3
- 金标准：`select round(avg(x),1) from (select salary_avg as x from jobs where salary_avg is not null order by x limit (select case when count(*)%2=1 then 1 else 2 end from jobs where salary_avg is not null) offset (select (count(*)-1)/2 from jobs where salary_avg is not null))`
- 模型：`SELECT ROUND(AVG(salary_avg), 1) AS 中位数
FROM (
    SELECT salary_avg AS x
    FROM jobs
    WHERE salary_avg IS NOT NULL
    ORDER BY x
    LIMIT 1
)`
- 错误：执行失败且自修复次数用尽：no such column: salary_avg

