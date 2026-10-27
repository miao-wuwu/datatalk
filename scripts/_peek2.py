import sqlite3
con = sqlite3.connect(r"D:\datatalk\data\jobs.db")
names = [r[0] for r in con.execute("select name from skills order by name")]
print(len(names), names)
