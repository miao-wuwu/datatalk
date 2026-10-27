"""用 headless Chrome（CDP）打开 DataTalk，真实跑一次提问并截图。

用法：python scripts/screenshot.py
产出：screenshots/home.png（首屏）、screenshots/result.png（一次问答后）
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


def shot(b: Browser, name: str) -> Path:
    data = b.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    path = OUT / name
    path.write_bytes(base64.b64decode(data["data"]))
    print(f"saved {path} ({path.stat().st_size // 1024} KB)")
    return path


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with Browser(port=9334, profile=str(Path(r"C:\Users\26690\AppData\Local\Temp\chr-datatalk"))) as b:
        b.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1100, "deviceScaleFactor": 1, "mobile": False})
        b.goto(URL, settle=3.0)
        print("title:", b.eval_js("document.title"))
        time.sleep(0.6)
        shot(b, "home.png")

        # 点第一个示例问题
        clicked = b.eval_js("(() => { const el = document.querySelector('.chip'); if (!el) return false; el.click(); return true; })()")
        print("clicked example:", clicked)
        for _ in range(60):
            time.sleep(1.0)
            n = b.eval_js("document.querySelectorAll('.card').length")
            if n:
                print("cards:", n)
                break
        else:
            print("timeout waiting for card")
        time.sleep(1.2)
        shot(b, "result.png")
        print("answer:", b.eval_js("(document.querySelector('.answer')||{}).textContent"))


if __name__ == "__main__":
    main()