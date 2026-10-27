import sys, time, json
sys.path.insert(0, r"D:\工作区\_scrape")
from cdp import Browser
from pathlib import Path

with Browser(port=9335, profile=r"C:\Users\26690\AppData\Local\Temp\chr-datatalk2") as b:
    b.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    b.goto("http://127.0.0.1:8100/", settle=3)
    b.eval_js("document.querySelector('.chip').click()")
    for _ in range(40):
        time.sleep(1)
        if b.eval_js("document.querySelectorAll('.card').length"):
            break
    time.sleep(1.5)
    audit = b.eval_js("""(() => {
      const q = s => document.querySelector(s);
      const rect = el => el ? [Math.round(el.getBoundingClientRect().width), Math.round(el.getBoundingClientRect().height)] : null;
      const canvas = q('.chart canvas');
      return {
        cards: document.querySelectorAll('.card').length,
        question: (q('.card-head h3')||{}).textContent,
        badge: (q('.badge')||{}).textContent,
        answer: (q('.answer')||{}).textContent,
        steps: [...document.querySelectorAll('.step')].map(e => e.textContent.trim()),
        tabs: [...document.querySelectorAll('.tab')].map(e => e.textContent.trim()),
        chartCanvas: rect(canvas),
        chartPixels: canvas ? [canvas.width, canvas.height] : null,
        tableRows: document.querySelectorAll('.result-table tbody tr').length,
        sqlVisible: !!q('.sql-body'),
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        cardRect: rect(q('.card')),
      };
    })()""")
    print(json.dumps(audit, ensure_ascii=False, indent=1))
