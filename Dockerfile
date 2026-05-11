# 单容器：构建前端静态资源 + 运行 FastAPI（适合 Render / Railway / Fly.io 等）
# 构建：在仓库根目录执行  docker build -t dota2-competition .
# 运行：平台注入 PORT；本地默认 8000

FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./backend/
# 内地构建时访问 files.pythonhosted.org 易超时，默认用清华 PyPI 镜像；海外构建可：
# docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple --build-arg PIP_TRUSTED_HOST=pypi.org .
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir --timeout 300 -i "${PIP_INDEX_URL}" \
    --trusted-host "${PIP_TRUSTED_HOST}" \
    -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /src/backend/static ./backend/static

WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
