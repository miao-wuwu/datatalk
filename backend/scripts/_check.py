import sqlite3, collections
con = sqlite3.connect(r"D:\datatalk\data\jobs.db")
c = collections.Counter(r[0] for r in con.execute("select city from jobs"))
print("city uniq", len(c))
print("weird cities:", [k for k in c if not (2 <= len(k) <= 4) or "," in k][:20])
print("top20", c.most_common(20))
print("--- salary")
vals = [r[0] for r in con.execute("select salary_avg from jobs where salary_avg is not null")]
print("n", len(vals), "min", min(vals), "p10", sorted(vals)[len(vals)//10], "median", sorted(vals)[len(vals)//2], "max", max(vals))
print("under50", sum(1 for v in vals if v < 50), "over1000", sum(1 for v in vals if v > 1000))
print("--- edu", collections.Counter(r[0] for r in con.execute("select education from jobs")).most_common(10))
print("--- days", collections.Counter(r[0] for r in con.execute("select days_per_week from jobs")).most_common(8))
print("--- months", collections.Counter(r[0] for r in con.execute("select months from jobs")).most_common(8))
