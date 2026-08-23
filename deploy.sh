#!/usr/bin/env bash
# ==============================================================================
#  国风教学助手 RAG v2.0 一键部署脚本（阿里云 2C2G + 1Panel / Nginx + systemd）
#  用法（ecs-assist-user NOPASSWD:sudo 环境）：
#     1. 在 SSH 会话里上传 teach-v2.tar.gz 到 $HOME
#        示例：cd 项目目录
#              scp teach-v2.tar.gz ecs-assist-user@47.97.115.209:~/
#     2. 解压：
#        sudo rm -rf /opt/teach-upgrade
#        sudo mkdir -p /opt/teach-upgrade
#        sudo tar -xzf ~/teach-v2.tar.gz --strip-components=1 -C /opt/teach-upgrade
#     3. 执行：
#        sudo bash /opt/teach-upgrade/deploy.sh 2>&1 | sudo tee /opt/teach-upgrade/deploy.log
#  回滚：
#     sudo systemctl stop teach
#     sudo cp -a /opt/teach/.backup-<时间戳>/* /opt/teach/
#     sudo systemctl start teach
# ==============================================================================
set -euo pipefail

# ================ 自动探测运行环境 / 兼容非 root 提权 ================
# 如果当前非 root，且可 sudo，则重新以 root 执行（保证整条链路同身份，避免权限链混用）
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    echo "[deploy] 非 root 身份，使用 sudo 重新执行本脚本..."
    exec sudo /usr/bin/env bash "$0" "$@"
  fi
  echo "[error] 当前非 root，且系统无 sudo，请切换 root 后执行" >&2
  exit 1
fi
echo "[deploy] 已获取 root 身份（uid=$(id -u)）"

# ---------------- 可修改参数 ----------------
APP_NAME="teach"
SERVICE_NAME="teach.service"
OLD_SERVICE_NAME="teachassist.service"                 # 老版本 v1 服务名：检测 + 健康检查通过后停止
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"          # 允许用户传环境变量覆盖生产目录
BACKUP_DIR="${BACKUP_DIR:-${INSTALL_DIR}/.backup-$(date +%Y%m%d-%H%M%S)}"
UPGRADE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # 本脚本所在目录即为升级包根
PY_BIN="${PY_BIN:-$(command -v python3 || command -v python)}"
USER_RUN="${USER_RUN:-root}"
UVICORN_HOST="127.0.0.1"
UVICORN_PORT="${UVICORN_PORT:-8777}"
WORKERS="${WORKERS:-1}"                                  # 2C2G 单 worker 足够
TIMEOUT="${TIMEOUT:-600}"                                # AI 流式生成需要较长超时
DEEPSEEK_API_KEY_PRESET="${DEEPSEEK_API_KEY_PRESET:-}"   # 可选：一键预设（优先用 SQLite 的值，这里仅兜底）
ZHIPU_API_KEY_PRESET="${ZHIPU_API_KEY_PRESET:-}"
# --------------------------------------------

log()  { printf "\033[1;32m[deploy]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m   %s\n" "$*" >&2; }
err()  { printf "\033[1;31m[error]\033[0m  %s\n" "$*" >&2; exit 1; }

# --------- 0. 基础环境检查 ---------
[ -n "$PY_BIN" ] || err "未发现 python3/python"
command -v systemctl       >/dev/null 2>&1 || warn "未发现 systemd, 将跳过服务管理, 需自行启动"
command -v nginx           >/dev/null 2>&1 || warn "未发现 nginx, 跳过 nginx -t"

PY_VER=$("$PY_BIN" -c 'import sys; print("%d.%d"%sys.version_info[:2])')
log "Python 版本: $PY_VER   (要求 3.10+)"
"$PY_BIN" -c 'import sys; assert sys.version_info >= (3,10), "Python <3.10"' 2>/dev/null \
    || err "Python 版本过低，需要 3.10 以上"

# --------- 1. 目录布局检查 ---------
[ -f "$UPGRADE_DIR/backend/app.py" ]          || err "升级包结构错误：缺少 backend/app.py（解压需 --strip-components=1）"
[ -f "$UPGRADE_DIR/frontend/index.html" ]     || err "升级包结构错误：缺少 frontend/index.html"
log "升级包 OK：$UPGRADE_DIR"
mkdir -p "$INSTALL_DIR"

# --------- 2. 备份当前版本（含数据库+向量库+上传文档） ---------
#    如果 v1 在 teachassist.service，则尝试从 systemd WorkingDirectory 定位真实目录并也备份
if systemctl list-unit-files --type=service --no-pager 2>/dev/null | grep -q "^${OLD_SERVICE_NAME}"; then
  OLD_WD=$(systemctl show -p WorkingDirectory --value "$OLD_SERVICE_NAME" 2>/dev/null || true)
  OLD_EXEC=$(systemctl show -p ExecStart --value "$OLD_SERVICE_NAME" 2>/dev/null | sed 's/^[^/]*//' | awk '{print $1}' || true)
  if [ -z "${OLD_WD:-}" ] || [ "$OLD_WD" = "[not set]" ]; then
    # 从 ExecStart 推断目录
    if [ -n "${OLD_EXEC:-}" ]; then OLD_WD=$(dirname "$(dirname "$OLD_EXEC")"); fi
  fi
  if [ -n "${OLD_WD:-}" ] && [ "$OLD_WD" != "$INSTALL_DIR" ] && [ -d "$OLD_WD" ]; then
    warn "检测到老版本 $OLD_SERVICE_NAME 实际工作目录 = $OLD_WD（与默认 $INSTALL_DIR 不同）"
    # 如果 INSTALL_DIR 还没东西，就把 INSTALL_DIR 对齐到老目录，保证部署不冲突
    if [ ! -d "$INSTALL_DIR/backend" ] && [ ! -d "$INSTALL_DIR/frontend" ] && [ -d "$OLD_WD/backend" -o -d "$OLD_WD/frontend" ]; then
      warn "→ 调整 INSTALL_DIR = $OLD_WD，将在老目录上就地升级 + 完整备份"
      INSTALL_DIR="$OLD_WD"
      BACKUP_DIR="${INSTALL_DIR}/.backup-$(date +%Y%m%d-%H%M%S)"
      mkdir -p "$INSTALL_DIR"
    fi
  fi
fi

if [ -d "$INSTALL_DIR/backend" ] || [ -d "$INSTALL_DIR/frontend" ]; then
  log "备份当前运行版本 → $BACKUP_DIR"
  mkdir -p "$BACKUP_DIR"
  for d in backend frontend requirements.txt .venv; do
    [ -e "$INSTALL_DIR/$d" ] && cp -a "$INSTALL_DIR/$d" "$BACKUP_DIR/" || true
  done
  if [ -f "$INSTALL_DIR/backend/app.db" ]; then
    mkdir -p "$BACKUP_DIR/backend"
    cp -a "$INSTALL_DIR/backend/app.db" "$BACKUP_DIR/backend/" 2>/dev/null || true
  fi
fi

# --------- 3. 写入代码（保留数据目录） ---------
log "同步 frontend / backend 代码 → $INSTALL_DIR"
DATA_TMP="$(mktemp -d /tmp/teach-data.XXXXXX)"
trap 'rm -rf "$DATA_TMP" || true' EXIT
if [ -d "$INSTALL_DIR/backend/data" ]; then
  cp -a "$INSTALL_DIR/backend/data" "$DATA_TMP/data"
fi

cp -a "$UPGRADE_DIR/frontend"   "$INSTALL_DIR/"
cp -a "$UPGRADE_DIR/backend"    "$INSTALL_DIR/"
[ -f "$UPGRADE_DIR/requirements.txt" ] && cp -a "$UPGRADE_DIR/requirements.txt" "$INSTALL_DIR/"

# 恢复数据目录（用户真实知识库 + 设置 + SQLite）
if [ -d "$DATA_TMP/data" ]; then
  rm -rf "$INSTALL_DIR/backend/data"
  cp -a "$DATA_TMP/data" "$INSTALL_DIR/backend/"
  rm -rf "$DATA_TMP/data"
fi
mkdir -p "$INSTALL_DIR/backend/data/documents"
# 给 www-data/ecs-assist-user 也可读（Nginx 静态资源 + 调试）
chmod -R a+rX "$INSTALL_DIR/frontend" 2>/dev/null || true

# --------- 4. 虚拟环境 + 依赖安装 ---------
VENV="$INSTALL_DIR/backend/.venv"
if [ ! -d "$VENV" ]; then
  log "创建虚拟环境 $VENV"
  "$PY_BIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "pip 升级 + 安装依赖（使用阿里云镜像加速）"
python -m pip install --quiet --upgrade pip setuptools wheel 2>&1 | tail -5 || true
python -m pip install --quiet -r "$INSTALL_DIR/requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 \
  | tail -20 || true

# 关键依赖校验
python -c 'import fastapi, uvicorn, langgraph, faiss, numpy, requests' \
  || err "关键依赖安装失败，请手动 pip install -r $INSTALL_DIR/requirements.txt"
log "依赖安装完成 ✅"

# --------- 5. 首次安装才 seed 示例知识库 ---------
cd "$INSTALL_DIR/backend"
if [ ! -f "data/app.db" ] && [ ! -f "data/vectorstore.pkl" ]; then
  log "首次部署：注入 10 篇示例文档 + GLM 向量（无 embed_key 则使用可复现伪向量兜底）"
  # 如果部署时预设了 Key，就作为临时 env 传给 seed
  if [ -n "$DEEPSEEK_API_KEY_PRESET" ]; then export DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY_PRESET"; fi
  if [ -n "$ZHIPU_API_KEY_PRESET" ];    then export ZHIPU_API_KEY="$ZHIPU_API_KEY_PRESET"; fi
  python seed_docs.py 2>&1 | tail -20 || warn "seed 失败，可在设置页「重建知识库」手动处理"
fi

# --------- 6. systemd 单元文件 ---------
UNIT_FILE="/etc/systemd/system/$SERVICE_NAME"
log "写入 systemd 单元 → $UNIT_FILE"
cat > "$UNIT_FILE" <<_SYSTEMD_
[Unit]
Description=Teach Assistant RAG v2 (FastAPI + FAISS + LangGraph)
After=network.target nginx.service

[Service]
Type=simple
User=${USER_RUN}
WorkingDirectory=${INSTALL_DIR}/backend
Environment=PYTHONUNBUFFERED=1
Environment=PATH=${INSTALL_DIR}/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# 可选：把 API Key 放在 systemd 环境，设置页将优先读取并脱敏显示
# Environment=DEEPSEEK_API_KEY=sk-xxx
# Environment=ZHIPU_API_KEY=xxx.xxx
# Environment=CITY_NAME=汉寿 CITY_LAT=28.914 CITY_LON=111.976  DAILY_WEATHER=true
ExecStart=${INSTALL_DIR}/backend/.venv/bin/python -m uvicorn app:app \
  --host ${UVICORN_HOST} \
  --port ${UVICORN_PORT} \
  --workers ${WORKERS} \
  --timeout-keep-alive ${TIMEOUT} \
  --log-level info \
  --proxy-headers \
  --forwarded-allow-ips '*'
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=teach-rag

[Install]
WantedBy=multi-user.target
_SYSTEMD_

systemctl daemon-reload || warn "daemon-reload 失败"
# 若老版本服务使用同一个 8777 → 先停 v1，避免端口冲突
if systemctl list-unit-files --type=service --no-pager 2>/dev/null | grep -q "^${OLD_SERVICE_NAME}"; then
  OLD_ACTIVE=$(systemctl is-active "$OLD_SERVICE_NAME" 2>/dev/null || true)
  if [ "$OLD_ACTIVE" = "active" ]; then
    OLD_PORT=$(ss -ltnp 2>/dev/null | grep "$(systemctl show -p MainPID --value "$OLD_SERVICE_NAME" 2>/dev/null || echo noop)" | awk '{print $4}' | grep -oE '[0-9]+$' | head -1 || true)
    log "检测到 $OLD_SERVICE_NAME 运行中 (端口=$OLD_PORT)"
    if [ "$OLD_PORT" = "$UVICORN_PORT" ]; then
      warn "$OLD_SERVICE_NAME 占用 $UVICORN_PORT 端口 → 先停止 v1（停失败不影响后续，稍后可手动 systemctl stop）"
      systemctl stop "$OLD_SERVICE_NAME" 2>/dev/null || true
      systemctl disable "$OLD_SERVICE_NAME" 2>/dev/null || true
    fi
  fi
fi

log "启用并重启 v2 服务 $SERVICE_NAME"
systemctl enable teach.service 2>/dev/null || true
systemctl restart teach.service
sleep 4
systemctl --no-pager --full status teach.service | head -15 || true

# --------- 7. 健康检查 ---------
log "健康检查 → http://127.0.0.1:${UVICORN_PORT}/api/health"
CODE="000"
for i in 1 2 3 4 5 6 7 8; do
  sleep 2
  CODE=$(curl -s -o /tmp/teach-health.json -w "%{http_code}" \
          --max-time 10 "http://127.0.0.1:${UVICORN_PORT}/api/health" || true)
  [ "$CODE" = "200" ] && break
done
if [ "$CODE" != "200" ]; then
  err "后端健康检查失败 HTTP=$CODE，请 journalctl -u teach -n 80 查看日志；若端口冲突请停 $OLD_SERVICE_NAME"
fi
"$PY_BIN" - <<'PY'  || true
import json
try:
  d = json.load(open('/tmp/teach-health.json'))
  print("   ok=", d.get('ok'),
        " version=", d.get('version'),
        " vector_chunks=", d.get('vector_stats',{}).get('total_chunks'),
        " docs=", d.get('vector_stats',{}).get('total_docs'),
        " llm_key=", d.get('has_llm_key'),
        " embed_key=", d.get('has_embed_key'))
except Exception as e:
  print("   json 解析异常:", e)
  print("   raw:", open('/tmp/teach-health.json').read()[:300])
PY

# --------- 8. Nginx 语法检查 + 1Panel 常用站点目录给出 location 建议 ---------
if command -v nginx >/dev/null 2>&1; then
  log "nginx -t"
  nginx -t 2>&1 | tail -3 || warn "nginx -t 失败，请检查 nginx /teach location"
  log "重载 nginx"
  systemctl reload nginx 2>/dev/null || true
fi
# 尝试把附随的 location 片段落地到 /etc/nginx/snippets/ 或 /www/server/panel/vhost/nginx/
SNIPPET_SRC="$UPGRADE_DIR/nginx-teach-location.conf"
for snippet_dir in /etc/nginx/snippets /www/server/panel/vhost/nginx; do
  if [ -d "$snippet_dir" ] && [ -f "$SNIPPET_SRC" ]; then
    cp -a "$SNIPPET_SRC" "${snippet_dir}/teach-v2-location.conf"
    log "Nginx location 片段已落地 → ${snippet_dir}/teach-v2-location.conf（需要站点配置里 include 或把内容贴到对应 server{} 里）"
  fi
done

# --------- 完成 ---------
echo
echo "======================================================================"
echo " 🎉 教学助手 v2 部署完成 "
echo " 运行目录    : $INSTALL_DIR"
echo " 备份目录    : $BACKUP_DIR"
echo " 本地健康    : http://127.0.0.1:${UVICORN_PORT}/api/health"
echo " 外网访问    : http://47.97.115.209/teach/"
echo " 查日志      : journalctl -u teach -n 100 -f"
echo " 服务启停    : systemctl start|stop|restart|status teach"
echo " 配置 Key    : 浏览器打开 设置与数据 → 粘贴 3 把 Key → 保存并测试"
echo "======================================================================"
