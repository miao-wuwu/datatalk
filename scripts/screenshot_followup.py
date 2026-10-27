"""截一张「多轮追问」的图：先问一个问题，点「在此追问」，再追问一句。

用法：python scripts/screenshot_followup.py
产出：screenshots/followup.png
"""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\工作区\_scrape")
from cdp import Browser  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
URL = "http://127.0.0.1:8100/"

ASK = """(() => {
  const input = document.querySelector('.ask-bar input');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, %s);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  document.querySelector('.ask-bar button').click();
  return true;
})()"""


def wait_cards(b: Browser, want: int, seconds: int = 90) -> int:
    for _ in range(seconds):
        time.sleep(1.0)
        n = b.eval_js("document.querySelectorAll('.card').length")
        if n >= want:
            return n
    return 0


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with Browser(port=9335, profile=str(Path(r"C:\Users\26690\AppData\Local\Temp\chr-datatalk2"))) as b:
        b.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1250, "deviceScaleFactor": 1, "mobile": False})
        b.goto(URL, settle=3.0)

        b.eval_js(ASK % '"杭州有多少个岗位？"')
        print("cards after q1:", wait_cards(b, 1))

        # 点最新卡片的「在此追问」
        clicked = b.eval_js(
            "(() => { const btn = [...document.querySelectorAll('.card-foot .ghost')][0];"
            " if (!btn) return false; btn.click(); return true; })()"
        )
        print("clicked follow-up:", clicked, "| chip:", b.eval_js("(document.querySelector('.followup')||{}).textContent"))

        b.eval_js(ASK % '"那深圳呢？"')
        print("cards after q2:", wait_cards(b, 2))
        time.sleep(1.5)

        print("rewritten:", b.eval_js("(document.querySelector('.rewritten')||{}).textContent"))
        data = b.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        path = OUT / "followup.png"
        path.write_bytes(base64.b64decode(data["data"]))
        print(f"saved {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()