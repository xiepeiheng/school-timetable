#!/usr/bin/env bash
#
# 部署脚本 — 在服务器上执行（默认 root）。
# 用法：
#   cd /opt/zhangyahan/school-timetable && ./deploy.sh
#
# 机密从 /opt/zhangyahan/school-timetable.env 读取（不提交 git）。
# 可用环境变量覆盖：SCHOOL_TIMETABLE_ENV / SCHOOL_TIMETABLE_WEBROOT
#
# 后端由 systemd 托管（deploy/school-timetable.service），不再依赖宝塔
# 「Python 项目」。Nginx 只负责静态文件和 /school-timetable/api/ 反代。

set -euo pipefail

SERVICE="school-timetable"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${SCHOOL_TIMETABLE_ENV:-/opt/zhangyahan/school-timetable.env}"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
WEBROOT="${SCHOOL_TIMETABLE_WEBROOT:-/www/wwwroot/xph.silyahuukou.cn/school-timetable}"
# systemd 服务运行用户（默认 www），需能读写 db.sqlite3 / logs / media
BACKEND_USER="${BACKEND_USER:-www}"
# uv 托管的 Python 安装目录（需对运行用户可读；默认 /opt/uv-python）
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/opt/uv-python}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

echo "=== 拉取最新代码 ==="
cd "${PROJECT_DIR}"
$SUDO git pull --ff-only

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
$SUDO chown "${BACKEND_USER}:${BACKEND_USER}" .env.production
echo "  → backend/.env.production 已生成"

if [ ! -d "${BACKEND_DIR}/.venv" ]; then
    echo "错误：${BACKEND_DIR}/.venv 不存在。请先在 backend/ 执行 uv sync。"
    exit 1
fi

uv sync --frozen
echo "  → Python 依赖已就绪"

uv run python manage.py migrate --noinput
echo "  → 数据库迁移完成"

# 代码可以归部署用户所有；只把运行用户需要写入的目录/文件交给 www。
# SQLite 会在 db.sqlite3 旁边创建 journal，因此 backend/ 目录本身也要可写。
$SUDO mkdir -p "${BACKEND_DIR}/logs" "${BACKEND_DIR}/media"
$SUDO chown -R "${BACKEND_USER}:${BACKEND_USER}" \
    "${BACKEND_DIR}/logs" "${BACKEND_DIR}/media"
if [ -f "${BACKEND_DIR}/db.sqlite3" ]; then
    $SUDO chown "${BACKEND_USER}:${BACKEND_USER}" "${BACKEND_DIR}/db.sqlite3"
fi
$SUDO chgrp "${BACKEND_USER}" "${BACKEND_DIR}"
$SUDO chmod 775 "${BACKEND_DIR}"
echo "  → backend 写权限已交给 ${BACKEND_USER}"

# -------------------------------------------------------------------
# 前端
# -------------------------------------------------------------------
echo "=== 构建前端 ==="

cd "${FRONTEND_DIR}"

# 重新载入机密（VITE_ 变量）
set -a; source "${SECRETS_FILE}"; set +a
envsubst < .env.production.template > .env.production
echo "  → frontend/.env.production 已生成"

npm ci --no-audit --no-fund
echo "  → Node 依赖已就绪"

npm run build-prod
echo "  → 前端已构建到 dist/"

echo "  → 复制到 ${WEBROOT} ..."
$SUDO mkdir -p "${WEBROOT}"
$SUDO rm -rf "${WEBROOT:?}"/*
$SUDO cp -r dist/* "${WEBROOT}/"
$SUDO chown -R www:www "${WEBROOT}"
echo "  → 网站根目录已更新"

# -------------------------------------------------------------------
# systemd 服务
# -------------------------------------------------------------------
echo "=== 安装 / 重启 ${SERVICE} ==="

# 防止旧的面板进程或其它程序占用 8014 导致服务起不来。
if ss -ltn 2>/dev/null | grep -q ':8014 '; then
    if ! $SUDO systemctl is-active --quiet "${SERVICE}"; then
        echo "错误：端口 8014 已被其他进程占用："
        ss -ltnp 2>/dev/null | grep ':8014 ' || true
        exit 1
    fi
fi

$SUDO install -m 0644 \
    "${PROJECT_DIR}/deploy/${SERVICE}.service" \
    "/etc/systemd/system/${SERVICE}.service"
$SUDO systemctl daemon-reload
$SUDO systemctl enable "${SERVICE}"
$SUDO systemctl restart "${SERVICE}"

sleep 2
if ! $SUDO systemctl is-active --quiet "${SERVICE}"; then
    echo "错误：${SERVICE} 启动失败。最近日志："
    $SUDO journalctl -u "${SERVICE}" -n 40 --no-pager || true
    exit 1
fi

$SUDO systemctl --no-pager --lines=5 status "${SERVICE}" || true

echo ""
echo "=== 部署完成 ==="
echo "查看日志：journalctl -u ${SERVICE} -f"
