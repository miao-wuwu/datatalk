import asyncio, sys, time
sys.path.insert(0, r"D:\datatalk\backend")
from app import pipeline

async def main():
    for q in ["北京招 Python 实习的公司有哪些？", "各城市的平均日薪是多少？", "本科和硕士岗位的平均薪资对比"]:
        t = time.perf_counter()
        r = await pipeline.ask(q)
        print("=" * 60)
        print("Q:", q, "| attempts:", r.attempts, "| conf:", r.confidence, "| err:", r.error)
        for s in r.steps:
            print("   ", s["name"], s["status"], "|", s["detail"][:90])
        print("SQL:", r.sql.replace("\n", " ")[:300])
        print("rows:", r.row_count, "| sample:", r.rows[:3])
        print("answer:", r.answer)
        print("elapsed: %.1fs" % (time.perf_counter() - t))

asyncio.run(main())
