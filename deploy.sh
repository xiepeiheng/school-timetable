#!/usr/bin/env bash
#
# 部署脚本 — 在服务器上执行（宝塔终端，默认 root）。
# 用法：
#   cd /opt/zhangyahan/school-timetable && ./deploy.sh
#
# 机密从 /opt/zhangyahan/school-timetable.env 读取（不提交 git）。
# 可用环境变量覆盖：SCHOOL_TIMETABLE_ENV / SCHOOL_TIMETABLE_WEBROOT

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${SCHOOL_TIMETABLE_ENV:-/opt/zhangyahan/school-timetable.env}"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
WEBROOT="${SCHOOL_TIMETABLE_WEBROOT:-/www/wwwroot/xph.silyahuukou.cn/school-timetable}"
# 后端运行用户（宝塔 Python 项目 gunicorn 的 user），需能读写 db.sqlite3 / logs
BACKEND_USER="${BACKEND_USER:-www}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

echo "=== 拉取最新代码 ==="
cd "${PROJECT_DIR}"
$SUDO git pull

# -------------------------------------------------------------------
# 后端
# -------------------------------------------------------------------
echo "=== 配置后端 ==="

if [ ! -f "${SECRETS_FILE}" ]; then
    echo "错误：找不到环境文件 ${SECRETS_FILE}。请先创建："
    echo "  cp ${PROJECT_DIR}/school-timetable.env.example ${SECRETS_FILE}"
    echo "  vim ${SECRETS_FILE}   # 填写真实值"
    exit 1
fi
set -a; source "${SECRETS_FILE}"; set +a

cd "${BACKEND_DIR}"
envsubst < .env.production.template > /tmp/st_env_production
$SUDO mv /tmp/st_env_production .env.production
echo "  → backend/.env.production 已生成"

uv sync
echo "  → Python 依赖已就绪"

uv run python manage.py migrate
echo "  → 数据库迁移完成"

# 交给后端运行用户，保证 db.sqlite3 / logs 可写
$SUDO chown -R "${BACKEND_USER}:${BACKEND_USER}" "${BACKEND_DIR}"
echo "  → backend 归属已设为 ${BACKEND_USER}"

# -------------------------------------------------------------------
# 前端
# -------------------------------------------------------------------
echo "=== 构建前端 ==="

cd "${FRONTEND_DIR}"

# 重新载入机密（VITE_ 变量）
set -a; source "${SECRETS_FILE}"; set +a
envsubst < .env.production.template > .env.production
echo "  → frontend/.env.production 已生成"

npm ci
echo "  → Node 依赖已就绪"

npm run build-prod
echo "  → 前端已构建到 dist/"

# 复制到网站根目录（Nginx 从此提供服务）
echo "  → 复制到 ${WEBROOT} ..."
$SUDO mkdir -p "${WEBROOT}"
$SUDO rm -rf "${WEBROOT:?}"/*
$SUDO cp -r dist/* "${WEBROOT}/"
$SUDO chown -R www:www "${WEBROOT}"
echo "  → 网站根目录已更新"

echo ""
echo "=== 部署完成 ==="
echo "请在宝塔面板中重启 school-timetable 项目（后端）。"
