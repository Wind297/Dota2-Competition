#!/usr/bin/env bash
# 在服务器上、仓库根目录执行：bash scripts/deploy-aliyun.sh
# 需先：cp scripts/deploy-aliyun.example.env scripts/deploy-aliyun.env 并编辑密码
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_FILE="${DEPLOY_ENV_FILE:-$REPO_ROOT/scripts/deploy-aliyun.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE"
  echo "请执行: cp scripts/deploy-aliyun.example.env scripts/deploy-aliyun.env"
  echo "然后编辑其中的 ADMIN_PASSWORD 与 SECRET_KEY。"
  exit 1
fi

HOST_PORT="${HOST_PORT:-8000}"
DATA_HOST_PATH="${DATA_HOST_PATH:-/root/dota2-data}"
IMAGE_NAME="${IMAGE_NAME:-dota2-competition}"
CONTAINER_NAME="${CONTAINER_NAME:-dota2-competition}"

sudo mkdir -p "$DATA_HOST_PATH"
sudo docker build -t "$IMAGE_NAME" "$REPO_ROOT"
sudo docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
sudo docker run -d --restart unless-stopped --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:8000" \
  --env-file "$ENV_FILE" \
  -v "${DATA_HOST_PATH}:/data" \
  "$IMAGE_NAME"

echo "已启动。浏览器访问: http://<本机公网IP>:${HOST_PORT}/"
echo "查看日志: sudo docker logs -f $CONTAINER_NAME"
