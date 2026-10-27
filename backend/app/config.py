"""全局配置。所有值都可用环境变量覆盖（见 .env.example）。"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # D:\datatalk
DB_PATH = Path(os.getenv("DATATALK_DB", ROOT / "data" / "jobs.db"))

# LLM（任意 OpenAI 兼容端点：Ollama /v1、DeepSeek、阿里百炼…）
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "studymate-qwen")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# 执行护栏
MAX_ROWS = int(os.getenv("MAX_ROWS", "200"))
QUERY_TIMEOUT = float(os.getenv("QUERY_TIMEOUT", "8"))
MAX_REPAIR = int(os.getenv("MAX_REPAIR", "2"))
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "300"))