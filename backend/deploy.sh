#!/usr/bin/env bash
# ==============================================================================
#  国风教学助手 RAG v2.0 一键部署脚本（阿里云 2C2G + 1Panel / Nginx + systemd）
#  用法：
#     1. 本项目打包为 teach-v2.tar.gz 后上传至服务器
#     2. 解压至 /opt/teach-upgrade (避免覆盖当前运行目录)
#     3. 切换 root：  sudo -i
#     4. 执行：       cd /opt/teach-upgrade && bash deploy.sh
#  回滚：         systemctl stop teach     && cp -a /opt/teach/.backup-<date>/* /opt/teach/
#                 systemctl start teach
# ==============================================================================
set -euo pipefail

# ---------------- 可修改参数 ----------------
APP_NAME="teach"
SERVICE_NAME="teach.service"
INSTALL_DIR="/opt/${APP_NAME}"                     # 生产运行目录（当前已部署位置）
BACKUP_DIR="/opt/${APP_NAME}/.backup-$(date +%Y%m%d-%H%M%S)"
UPGRADE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # 本脚本所在目录即为升级包根
PY_BIN="${PY_BIN:-python3}"
USER_RUN="${USER_RUN:-root}"
UVICORN_HOST="127.0.0.1"
UVICORN_PORT="8777"
WORKERS="${WORKERS:-1}"                              # 2C2G 单 worker 足够
TIMEOUT="${TIMEOUT:-600}"                            # AI 流式生成需要较长超时
# --------------------------------------------

log()  { printf "\033[1;32m[deploy]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m   %s\n" "$*" >&2; }
err()  { printf "\033[1;31m[error]\033[0m  %s\n" "$*" >&2; exit 1; }

# --------- 0. 基础环境检查 ---------
command -v "$PY_BIN"       >/dev/null 2>&1 || err "未发现 $PY_BIN, 请先安装 python3.10+"
command -v systemctl       >/dev/null 2>&1 || warn "未发现 systemd, 将跳过服务管理, 需自行启动"
command -v nginx           >/dev/null 2>&1 || warn "未发现 nginx, 跳过 nginx -t"

PY_VER=$("$PY_BIN" -c 'import sys; print("%d.%d"%sys.version_info[:2])')
log "Python 版本: $PY_VER   (要求 3.10+)"
"$PY_BIN" -c 'import sys; assert sys.version_info >= (3,10), "Python <3.10"' 2>/dev/null \
    || err "Python 版本过低，需要 3.10 以上"

# --------- 1. 目录布局检查 ---------
[ -f "$UPGRADE_DIR/backend/app.py" ]          || err "升级包结构错误：缺少 backend/app.py"
[ -f "$UPGRADE_DIR/frontend/index.html" ]     || err "升级包结构错误：缺少 frontend/index.html"
log "升级包 OK：$UPGRADE_DIR"

mkdir -p "$INSTALL_DIR"

# --------- 2. 备份当前版本（含数据库+向量库+上传文档） ---------
if [ -d "$INSTALL_DIR/backend" ] || [ -d "$INSTALL_DIR/frontend" ]; then
  log "备份当前运行版本 → $BACKUP_DIR"
  mkdir -p "$BACKUP_DIR"
  for d in backend frontend requirements.txt; do
    [ -e "$INSTALL_DIR/$d" ] && cp -a "$INSTALL_DIR/$d" "$BACKUP_DIR/" || true
  done
  # 数据目录单独保留（SQLite + 向量库 + 上传文档），本次升级不覆盖
  if [ -d "$INSTALL_DIR/backend/data" ]; then
    mkdir -p "$BACKUP_DIR/backend"
    cp -a "$INSTALL_DIR/backend/data" "$BACKUP_DIR/backend/"
  fi
fi

# --------- 3. 写入代码（保留数据目录） ---------
log "同步 frontend / backend 代码 → $INSTALL_DIR"

# 3.1 若存在数据，先暂存到安全位置，防止覆盖
DATA_TMP="$(mktemp -d /tmp/teach-data.XXXXXX)"
trap 'rm -rf "$DATA_TMP" || true' EXIT
if [ -d "$INSTALL_DIR/backend/data" ]; then
  cp -a "$INSTALL_DIR/backend/data" "$DATA_TMP/data"
fi

# 3.2 整体复制（可能覆盖 data，但没关系，我们暂存了）
cp -a "$UPGRADE_DIR/frontend"   "$INSTALL_DIR/"
cp -a "$UPGRADE_DIR/backend"    "$INSTALL_DIR/"
[ -f "$UPGRADE_DIR/requirements.txt" ] && cp -a "$UPGRADE_DIR/requirements.txt" "$INSTALL_DIR/"

# 3.3 恢复数据目录（用户真实知识库 + 设置 + SQLite）
if [ -d "$DATA_TMP/data" ]; then
  rm -rf "$INSTALL_DIR/backend/data"
  cp -a "$DATA_TMP/data" "$INSTALL_DIR/backend/"
  rm -rf "$DATA_TMP/data"
fi

# 确保目录存在
mkdir -p "$INSTALL_DIR/backend/data/documents"

# --------- 4. 虚拟环境 + 依赖安装 ---------
VENV="$INSTALL_DIR/backend/.venv"
if [ ! -d "$VENV" ]; then
  log "创建虚拟环境 $VENV"
  "$PY_BIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "pip 升级 + 安装依赖（使用阿里云镜像加速）"
pip install --quiet --upgrade pip 2>&1 | tail -5 || true
pip install --quiet -r "$INSTALL_DIR/requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 \
  | tail -20 || true

# 关键依赖校验
python -c 'import fastapi, uvicorn, langgraph, faiss, numpy, requests' \
  || err "关键依赖安装失败，请手动 pip install -r $INSTALL_DIR/requirements.txt"
log "依赖安装完成 ✅"

# --------- 5. 首次安装才 seed 示例知识库（仅当向量库 + SQLite 均不存在时） ---------
cd "$INSTALL_DIR/backend"
if [ ! -f "data/app.db" ] && [ ! -f "data/vectorstore.pkl" ]; then
  log "首次部署：注入 10 篇示例文档 + GLM 向量（需要 ZHIPU_API_KEY 环境变量，无 key 则用可复现伪向量以保证可用）"
  python seed_docs.py 2>&1 | tail -15 || warn "seed 失败，可后续通过设置页「重建知识库」手动处理"
fi

# --------- 6. systemd 单元文件 ---------
UNIT_FILE="/etc/systemd/system/$SERVICE_NAME"
log "写入 systemd 单元 → $UNIT_FILE"
cat > "$UNIT_FILE" <<'_SYSTEMD_'
[Unit]
Description=Teach Assistant RAG v2 (FastAPI + FAISS + LangGraph)
After=network.target nginx.service

[Service]
Type=simple
User=__USER_RUN__
WorkingDirectory=__INSTALL_DIR__/backend
Environment=PYTHONUNBUFFERED=1
Environment=PATH=__INSTALL_DIR__/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# 可选：把 API Key 放在 systemd 环境，设置页将优先读取并脱敏显示
# Environment=DEEPSEEK_API_KEY=sk-xxx
# Environment=ZHIPU_API_KEY=xxx.xxx
# Environment=CITY_NAME=汉寿 CITY_LAT=28.914 CITY_LON=111.976  DAILY_WEATHER=true
ExecStart=__INSTALL_DIR__/backend/.venv/bin/python -m uvicorn app:app \
  --host __UVICORN_HOST__ \
  --port __UVICORN_PORT__ \
  --workers __WORKERS__ \
  --timeout-keep-alive __TIMEOUT__ \
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

# 替换占位符
sed -i "s|__USER_RUN__|${USER_RUN}|g"                 "$UNIT_FILE"
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g"           "$UNIT_FILE"
sed -i "s|__UVICORN_HOST__|${UVICORN_HOST}|g"         "$UNIT_FILE"
sed -i "s|__UVICORN_PORT__|${UVICORN_PORT}|g"         "$UNIT_FILE"
sed -i "s|__WORKERS__|${WORKERS}|g"                   "$UNIT_FILE"
sed -i "s|__TIMEOUT__|${TIMEOUT}|g"                   "$UNIT_FILE"

systemctl daemon-reload || warn "daemon-reload 失败，非 systemd 环境请手动启动"
if command -v systemctl >/dev/null 2>&1; then
  log "重启 teach 服务"
  systemctl enable teach.service 2>/dev/null || true
  systemctl restart teach.service
  sleep 3
  systemctl --no-pager --full status teach.service | head -15 || true
fi

# --------- 7. 健康检查 ---------
log "健康检查 → http://127.0.0.1:${UVICORN_PORT}/api/health"
for i in 1 2 3 4 5; do
  sleep 2
  CODE=$(curl -s -o /tmp/teach-health.json -w "%{http_code}" \
          --max-time 10 "http://127.0.0.1:${UVICORN_PORT}/api/health" || true)
  [ "$CODE" = "200" ] && break
done
if [ "$CODE" != "200" ]; then
  err "后端健康检查失败 HTTP=$CODE，请 journalctl -u teach -n 50 查看日志"
fi
python - <<'PY'  || true
import json
d = json.load(open('/tmp/teach-health.json'))
print("   ok=", d.get('ok'),
      " version=", d.get('version'),
      " vector_chunks=", d.get('vector_stats',{}).get('total_chunks'),
      " docs=", d.get('vector_stats',{}).get('total_docs'),
      " llm_key=", d.get('has_llm_key'),
      " embed_key=", d.get('has_embed_key'))
PY

# --------- 8. Nginx 语法检查 ---------
if command -v nginx >/dev/null 2>&1; then
  log "nginx -t"
  nginx -t 2>&1 | tail -3 || warn "nginx -t 失败，请检查 /etc/nginx/conf.d/ 或 /www/server/panel/vhost/nginx/ 中的 /teach location"
  log "重载 nginx (若使用 1Panel 请在面板重载，效果相同)"
  systemctl reload nginx 2>/dev/null || true
fi

# --------- 完成 ---------
echo
echo "======================================================================"
echo " 🎉 教学助手 v2 部署完成 "
echo " 本地健康  : http://127.0.0.1:${UVICORN_PORT}/api/health"
echo " 外网访问  : http://47.97.115.209/teach/"
echo " 启动命令  : systemctl start teach      (stop/status/restart 同理)"
echo " 查日志    : journalctl -u teach -n 100 -f"
echo " 回滚方法  : cp -a $BACKUP_DIR/* /opt/teach/ && systemctl restart teach"
echo " 配置 Key  : 浏览器访问 设置与数据 → 粘贴 3 把 Key → 点「保存并测试」"
echo "             或 在 /etc/systemd/system/teach.service 中取消 Environment= 行注释"
echo "======================================================================"
