import sys
sys.path.insert(0, r"D:\datatalk\backend")
from app import db
tests = [
 "SELECT jobs.industry AS x, ROUND(AVG(jobs.salary_avg),1) FROM jobs WHERE salary_avg IS NOT NULL GROUP BY jobs.industry",
 "SELECT COUNT(DISTINCT j.id) FROM jobs j JOIN job_skills js ON j.id=js.job_id JOIN skills s ON js.skill_id=s.id WHERE s.name='Python' AND s.name='Agent'",
 "SELECT c.industry AS x FROM companies c WHERE c.industry='汽车行业'",
]
for t in tests:
    print("lint:", db.lint(t))
