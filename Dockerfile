# syntax=docker/dockerfile:1
# DataTalk：一个镜像里同时装前端静态文件和 FastAPI 后端
# 用法：docker build -t datatalk . && docker run --rm -p 8100:8100 \
#         -e LLM_BASE_URL=http://host.docker.internal:11434/v1 datatalk

# ---------- 1. 构建前端 ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. 运行镜像 ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ ./backend/
COPY data/jobs.db ./data/jobs.db
COPY --from=web /web/dist ./frontend/dist

# 默认连宿主机的 Ollama；换成任何 OpenAI 兼容端点都行
ENV DATATALK_DB=/app/data/jobs.db \
    LLM_BASE_URL=http://host.docker.internal:11434/v1 \
    LLM_MODEL=studymate-qwen

EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8100/api/health',timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--app-dir", "backend"]