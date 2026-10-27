import json
d = json.load(open(r"D:\datatalk\data\_smoke.json", encoding="utf-8"))
for r in d["results"]:
    if not r["strict"]:
        print(f"#{r['id']} [{r['kind']}] {r['question']}")
        print("  gold:", r["sample_gold"], " got:", r["sample_got"])
        print("  sql :", " ".join(r["sql"].split())[:260])
        print()
