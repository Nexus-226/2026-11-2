#!/usr/bin/env bash
# 在 ECS 上执行（root 或 sudo）：装依赖、拉代码、配后端与 nginx。
# 前提：frontend/dist 已上传，或前端已在服务器构建。
set -euo pipefail

APP_DIR=/opt/pet-agent
REPO_URL=https://github.com/Nexus-226/Pet_Agent.git

echo "==> 安装系统依赖"
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx git ffmpeg

echo "==> 拉取代码"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull
fi

echo "==> 安装后端依赖"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR/backend"

echo "==> 准备数据目录"
mkdir -p /var/lib/pet-agent
chown -R www-data /var/lib/pet-agent
install -d -m 0700 -o www-data -g www-data "$APP_DIR/vlog-media"

echo "==> 配置 systemd 后端服务"
cp "$APP_DIR/deploy/pet-agent.service" /etc/systemd/system/pet-agent.service
systemctl daemon-reload
systemctl enable --now pet-agent

echo "==> 配置 nginx"
mkdir -p "$APP_DIR/frontend/dist"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/pet-agent
ln -sf /etc/nginx/sites-available/pet-agent /etc/nginx/sites-enabled/pet-agent
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 完成。访问 http://<公网IP>/ 验证（安全组需放行 80）。"
