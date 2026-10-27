import json
d = json.load(open(r"D:\datatalk\data\_smoke.json", encoding="utf-8"))
for r in d["results"][:2]:
    print(r["question"])
    print("error:", r["error"][:400])
    print("sql:", r["sql"][:400])
    print("---")
