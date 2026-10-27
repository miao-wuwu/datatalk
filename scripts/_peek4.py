import json
d = json.load(open(r"D:\datatalk\data\eval_result.json", encoding="utf-8"))
fails = [r for r in d["results"] if not r["strict"]]
for r in fails:
    print(f"#{r['id']} [{r['kind']}] {r['question']}  gold/got={r['gold_rows']}/{r['got_rows']}")
    print("  gold:", " | ".join(str(x) for x in r["sample_gold"]))
    print("  got :", " | ".join(str(x) for x in r["sample_got"]))
    print()
