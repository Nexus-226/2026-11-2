#!/usr/bin/env bash
# 在本地执行：构建前端（API 模式），把 dist/ 和 deploy/ 上传到 ECS，并执行远程安装。
# 用法：./build-and-upload.sh <ECS公网IP> [SSH用户名=root]
set -euo pipefail

ECS_IP="${1:?用法: ./build-and-upload.sh <ECS公网IP> [SSH用户]}"
SSH_USER="${2:-root}"
APP_DIR=/opt/pet-agent

cd "$(dirname "$0")/.."

echo "==> 构建前端（API 模式）"
cd frontend
cat > .env.production <<'EOF'
VITE_CHAT_DATA_SOURCE=api
VITE_PET_DATA_SOURCE=api
VITE_RECORD_DATA_SOURCE=api
VITE_REMINDER_DATA_SOURCE=api
EOF
npm install
npm run build
cd ..

echo "==> 上传 dist/ 和 deploy/ 到 ECS"
ssh "${SSH_USER}@${ECS_IP}" "mkdir -p ${APP_DIR}/frontend ${APP_DIR}/deploy"
scp -r frontend/dist "${SSH_USER}@${ECS_IP}:${APP_DIR}/frontend/"
scp -r deploy/* "${SSH_USER}@${ECS_IP}:${APP_DIR}/deploy/"

echo "==> 在 ECS 上执行安装脚本"
ssh "${SSH_USER}@${ECS_IP}" "bash ${APP_DIR}/deploy/setup-remote.sh"
