import json
d = json.load(open(r"D:\datatalk\data\eval_result.json", encoding="utf-8"))
want = {13,17,42,49,50,73,97,99,92,55}
for r in d["results"]:
    if r["id"] in want:
        print(f"#{r['id']} {r['question']}")
        print("MODEL:", " ".join(r["sql"].split())[:400])
        print()
