import json
d = json.load(open(r"D:\datatalk\data\eval_result.json", encoding="utf-8"))
want = {63,66,74,96,61,58,31,40}
for r in d["results"]:
    if r["id"] in want:
        print(f"#{r['id']} {r['question']}  attempts={r['attempts']} kind={r['kind']}")
        print("  err:", (r["error"] or "")[:300])
        print("  sql:", " ".join(r["sql"].split())[:300])
        print("  got:", r["sample_got"][:2], " gold:", r["sample_gold"][:2])
        print()
