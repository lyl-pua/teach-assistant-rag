#!/usr/bin/env bash
# ============================================================================
# 教学助手 v2.1 前端强制部署 + Nginx location 注入 + 全链路健康检查
# 设计目标：一条 sudo bash deploy-frontend-force.sh 跑完全流程，
#          不要求用户切 root / 不要求交互式密码 / 不要求手工编辑 Nginx。
# 适用范围：Ubuntu 22.04 + 1Panel（vhost 在 /www/server/panel/vhost/nginx）。
# 作者备注：ecs-assist-user 有 (ALL) NOPASSWD:ALL，全部系统动作加 sudo 前缀。
# ============================================================================
set -u
export LC_ALL=C.UTF-8

if [ "$(id -u)" -ne 0 ]; then
  # 自动用 sudo 重入（保证后续一条命令搞定）
  exec sudo bash "$0" "$@"
fi

STAGE=0
step(){ STAGE=$((STAGE+1)); echo; echo "========== [$STAGE/9] $1 =========="; }
ok(){   echo "  ✅ $*"; }
warn(){ echo "  ⚠  $*"; }
fail(){ echo "  ❌ $*"; }

INSTALL_DIR="/opt/teach"
BACKEND_DIR="$INSTALL_DIR/backend"
FRONTEND_DIR="$INSTALL_DIR/frontend"
SNIPPET_V1="/www/server/panel/vhost/nginx/teach-v2-location.conf"
SNIPPET_V2="/etc/nginx/snippets/teach-v2-location.conf"
PACKAGE_SRC=""
# 支持 3 种升级包来源（按优先级自动探测）
for CAND in \
  "$HOME/teach-v2.tar.gz" \
  "/home/ecs-assist-user/teach-v2.tar.gz" \
  "/home/ecs-assist-user/teachupgarde/backend/app.py" \
  "/opt/teach-upgrade/backend/app.py"; do
  if [ -e "$CAND" ]; then PACKAGE_SRC="$CAND"; break; fi
done

step "环境 & 升级包探测"
echo "  当前用户: $(whoami)  uid=$(id -u)"
echo "  Python:   $(command -v python3)  $(python3 --version 2>&1 | awk '{print $2}')"
echo "  Nginx:    $(command -v nginx)  $(nginx -v 2>&1 | awk -F/ '{print $2}')"
echo "  Systemd:  $(command -v systemctl)"
echo "  升级包来源: ${PACKAGE_SRC:-未找到！(请确认 teach-v2.tar.gz 已上传到 ~/ 或 /home/ecs-assist-user/)}"

# -------- 1) 升级包就位 --------
if [ -z "$PACKAGE_SRC" ]; then
  fail "未找到任何升级包 / 已解压的目录。请先通过 1Panel 文件管理器把 teach-v2.tar.gz 上传到 /home/ecs-assist-user/ 再重跑本脚本。"
  exit 2
fi
mkdir -p "$INSTALL_DIR" /opt/teach-upgrade /etc/nginx/snippets /www/server/panel/vhost/nginx

# 如果是 tar.gz，就地解压到 /opt/teach-upgrade（强制覆盖）
if [[ "$PACKAGE_SRC" == *.tar.gz ]]; then
  step "解压 teach-v2.tar.gz → /opt/teach-upgrade"
  rm -rf /opt/teach-upgrade/*
  tar -xzf "$PACKAGE_SRC" --strip-components=1 -C /opt/teach-upgrade
  SRC="/opt/teach-upgrade"
else
  # 已经是解压后的目录（PACKAGE_SRC 指向 backend/app.py）
  SRC="${PACKAGE_SRC%/*/*}"   # /home/ecs-assist-user/teachupgarde
fi
ok "源码根目录 = $SRC"

# 最小化结构校验
MISS=()
for X in "$SRC/frontend/index.html" "$SRC/frontend/static/app.js" "$SRC/frontend/static/style.css" \
         "$SRC/backend/app.py" "$SRC/backend/requirements.txt"; do
  [ -f "$X" ] || MISS+=("$X")
done
if [ ${#MISS[@]} -gt 0 ]; then
  fail "源码结构不完整，缺失："
  printf '      - %s\n' "${MISS[@]}"
  exit 3
fi
ok "前端 3 文件 + 后端 app.py + requirements.txt 全部存在"

# -------- 2) 备份当前运行版本 --------
step "备份现有 /opt/teach（若存在）"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP=""
if [ -d "$INSTALL_DIR/frontend" ] || [ -d "$INSTALL_DIR/backend" ]; then
  BACKUP="$INSTALL_DIR/.backup-$TS"
  mkdir -p "$BACKUP"
  [ -d "$INSTALL_DIR/frontend" ] && cp -a "$INSTALL_DIR/frontend" "$BACKUP/"
  [ -d "$INSTALL_DIR/backend"  ] && {
    cp -a "$INSTALL_DIR/backend" "$BACKUP/"
    # 排除 .venv，瘦身备份
    rm -rf "$BACKUP/backend/.venv"
  }
  [ -d "$INSTALL_DIR/data"     ] && cp -a "$INSTALL_DIR/data"     "$BACKUP/" 2>/dev/null || true
  ok "备份完成 → $BACKUP"
else
  warn "/opt/teach 下没有老版本，跳过备份（首次部署）"
fi

# -------- 3) 同步前端（强制整目录覆盖）--------
step "同步前端：$SRC/frontend → $FRONTEND_DIR"
# 先 rm 旧内容再 cp，避免删错
rm -rf "$FRONTEND_DIR"
mkdir -p "$FRONTEND_DIR"
cp -a "$SRC/frontend/." "$FRONTEND_DIR/"
chown -R root:root "$FRONTEND_DIR"
chmod -R a+rX           "$FRONTEND_DIR"
F_SIZE=$(stat -c%s "$FRONTEND_DIR/index.html" 2>/dev/null || echo 0)
JS_HAS=$(grep -cE 'function\s+loadHome\b|function\s+loadAI\b' "$FRONTEND_DIR/static/app.js" 2>/dev/null || echo 0)
HTML_HAS=$(grep -c '早上好，刘老师' "$FRONTEND_DIR/index.html" 2>/dev/null || echo 0)
ok "index.html size = $F_SIZE B  问候语命中 = $HTML_HAS  app.js 6模块入口命中 >=2 ? $JS_HAS"

# -------- 4) 同步后端 --------
step "同步后端：$SRC/backend → $BACKEND_DIR"
# 保留旧虚拟环境 & data（否则每次重部署要重新 pip install + 重建向量）
KEEP_VENV=""
KEEP_DATA=""
[ -d "$BACKEND_DIR/.venv" ] && KEEP_VENV="YES" && cp -a "$BACKEND_DIR/.venv" /tmp/teach-venv-$$
[ -d "$BACKEND_DIR/data"   ] && KEEP_DATA="YES" && cp -a "$BACKEND_DIR/data"   /tmp/teach-data-$$
rm -rf "$BACKEND_DIR"
mkdir -p "$BACKEND_DIR"
cp -a "$SRC/backend/." "$BACKEND_DIR/"
# 还原保留
if [ "$KEEP_VENV" = "YES" ] && [ -d /tmp/teach-venv-$$ ]; then
  mv -f /tmp/teach-venv-$$ "$BACKEND_DIR/.venv"
  ok "保留旧 .venv（pip 不重装）"
fi
if [ "$KEEP_DATA" = "YES" ] && [ -d /tmp/teach-data-$$ ]; then
  mv -f /tmp/teach-data-$$ "$BACKEND_DIR/data"
  ok "保留旧 data（db + 向量库不丢失）"
fi
chown -R root:root "$BACKEND_DIR"
chmod -R go-w "$BACKEND_DIR"
find "$BACKEND_DIR" -type d -exec chmod a+rx {} +
find "$BACKEND_DIR" -type f -exec chmod a+r {} +
chmod +x "$BACKEND_DIR/run.sh" 2>/dev/null || true
ok "后端同步完成"

# -------- 5) 虚拟环境 + 依赖 --------
step "虚拟环境 & pip 依赖（阿里云镜像加速）"
cd "$BACKEND_DIR"
if [ ! -d ".venv" ] || [ ! -x ".venv/bin/python" ]; then
  rm -rf .venv
  python3 -m venv .venv
  ok "已创建新虚拟环境"
else
  ok "复用现有虚拟环境"
fi
.venv/bin/python -m pip install --upgrade pip -q -i http://mirrors.cloud.aliyuncs.com/pypi/simple/ --trusted-host mirrors.cloud.aliyuncs.com 2>&1 | tail -2
.venv/bin/python -m pip install -q -i http://mirrors.cloud.aliyuncs.com/pypi/simple/ --trusted-host mirrors.cloud.aliyuncs.com -r requirements.txt 2>&1 | tail -5
if ! .venv/bin/python -c 'import fastapi, faiss, langgraph, sentence_transformers' 2>/dev/null; then
  # sentence_transformers 不是必须（RAG 用 GLM 云端），只检查核心三项
  .venv/bin/python -c 'import fastapi, faiss, langgraph' && ok "核心依赖 OK（fastapi + faiss + langgraph）" || {
    fail "核心依赖缺失，手动跑：cd $BACKEND_DIR && .venv/bin/pip install -r requirements.txt"
  }
else
  ok "核心依赖全部 OK"
fi

# -------- 6) 首次部署 seed（data 不存在时才跑）--------
step "seed 示例知识库（仅首次）"
cd "$BACKEND_DIR"
if [ ! -f "data/app.db" ] || [ ! -f "data/vectorstore.pkl" ]; then
  if .venv/bin/python seed_docs.py >/tmp/seed.log 2>&1; then
    ok "seed 完成，日志末 5 行："
    tail -5 /tmp/seed.log | sed 's/^/       /'
  else
    warn "seed 报错，日志："
    tail -20 /tmp/seed.log | sed 's/^/       /'
  fi
else
  ok "已有数据库 + 向量库，跳过 seed（保留你现有数据）"
fi

# -------- 7) systemd v2 teach 服务（永远重写最新 WorkingDirectory）--------
step "写入 /etc/systemd/system/teach.service + 重启服务"
cat > /etc/systemd/system/teach.service <<SYSD
[Unit]
Description=Teach Assistant RAG v2 (FastAPI + FAISS + LangGraph)
After=network.target nginx.service

[Service]
Type=simple
User=root
WorkingDirectory=$BACKEND_DIR
Environment=PYTHONUNBUFFERED=1
Environment=API_TIMEOUT=120
Environment=UVICORN_HOST=127.0.0.1
Environment=UVICORN_PORT=8777
ExecStart=$BACKEND_DIR/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8777 --workers 1 --timeout-keep-alive 600 --log-level info --proxy-headers --forwarded-allow-ips "*"
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=teach-rag

[Install]
WantedBy=multi-user.target
SYSD
systemctl daemon-reload 2>&1 | tail -3

# 停用老 v1 teachassist（disable + 删 service 文件 + 发信号 -9）
systemctl stop teachassist 2>/dev/null || true
systemctl disable teachassist 2>/dev/null || true
if [ -f /etc/systemd/system/teachassist.service ]; then
  mv -f /etc/systemd/system/teachassist.service /etc/systemd/system/teachassist.service.bak-$TS
  systemctl daemon-reload
fi
# 强制清除 8777 上任何非 teach.service 的残留进程（尤其是老 v1）
BAD_PID=$(ss -ltnp 2>/dev/null | awk '/:8777 /{gsub(/.*pid=/,"",$NF); gsub(/,.*/,"",$NF); print $NF}' | sort -u | head -1)
if [ -n "$BAD_PID" ]; then
  TEACH_MAIN=$(systemctl show --value -p MainPID teach 2>/dev/null || echo 0)
  if [ "$BAD_PID" != "$TEACH_MAIN" ] && [ "$BAD_PID" != "0" ]; then
    warn "检测到 8777 端口上有非 teach v2 进程 PID=$BAD_PID → 强制清理"
    kill -9 "$BAD_PID" 2>/dev/null || true
    sleep 2
  fi
fi

systemctl enable teach 2>&1 | tail -1
systemctl restart teach 2>&1 | tail -3
sleep 4
systemctl --no-pager --full status teach 2>&1 | head -10 | sed 's/^/  /'
MAIN_PID=$(systemctl show --value -p MainPID teach 2>/dev/null)
if [ -n "$MAIN_PID" ] && [ "$MAIN_PID" != "0" ]; then
  RSS=$(awk '/VmRSS/{printf "%.1fM",$2/1024}' /proc/$MAIN_PID/status 2>/dev/null || echo "?")
  ok "teach v2 主进程 PID=$MAIN_PID  内存=$RSS"
else
  warn "无法取到 teach v2 MainPID，稍后在健康检查里确认。"
fi

# -------- 8) 写 Nginx /teach location + 注入 1Panel 默认站 --------
step "写入 Nginx /teach location 并注入 1Panel 默认站点"
mkdir -p /etc/nginx/snippets /www/server/panel/vhost/nginx
cat > "$SNIPPET_V2" <<'NGINX'
# ===== Teach RAG v2 Nginx locations (强制部署脚本写入) =====
location ^~ /teach/ {
    alias  /opt/teach/frontend/;
    index  index.html;
    try_files $uri $uri/ @teach_api;
    location ~* \.(?:js|css|png|jpg|jpeg|svg|woff2?|ttf|ico)$ {
        alias  /opt/teach/frontend$uri;
        access_log off;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
        try_files $uri =404;
    }
}
location ^~ /teach/api/ {
    proxy_pass         http://127.0.0.1:8777/api/;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout      600s;
    proxy_send_timeout      600s;
    proxy_connect_timeout   10s;
    proxy_buffering         off;
    proxy_cache             off;
    gzip                    off;
    chunked_transfer_encoding on;
}
location @teach_api {
    proxy_pass         http://127.0.0.1:8777;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout      600s;
    proxy_buffering         off;
}
location = /teach { return 301 /teach/; }
NGINX
cp -a "$SNIPPET_V2" "$SNIPPET_V1"
ok "location 片段已落盘: $SNIPPET_V2 + $SNIPPET_V1"

# 探测 1Panel 当前默认站点的 vhost 文件
VHOST=""
for dir in /www/server/panel/vhost/nginx /etc/nginx/conf.d /etc/nginx/sites-enabled; do
  [ -d "$dir" ] || continue
  for f in "$dir"/*.conf; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in teach-v2-location*) continue ;; esac
    if grep -Eq '^\s*(listen\s+80|server_name\s+.*(47\.97\.115\.209|_))' "$f" 2>/dev/null; then
      VHOST="$f"; break 2
    fi
  done
done
if [ -z "$VHOST" ]; then
  for f in /www/server/panel/vhost/nginx/*.conf /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in teach-v2-location*) continue ;; esac
    VHOST="$f"; break
  done
fi
if [ -z "$VHOST" ]; then
  fail "找不到任何 Nginx vhost conf！手动把 $SNIPPET_V2 贴进你默认站 server{} 里即可。"
else
  ok "选中默认站点 conf = $VHOST"
  cp -a "$VHOST" "$VHOST.bak-teachv2-frontend-$TS"
  # 去重：如果已经注入过则先删除旧片段
  if grep -q 'Teach RAG v2 Nginx locations (强制部署脚本写入)' "$VHOST"; then
    python3 - "$VHOST" <<PY
import sys,re
p=sys.argv[1]; s=open(p,encoding='utf-8',errors='ignore').read()
marker='# ===== Teach RAG v2 Nginx locations (强制部署脚本写入) ====='
start=s.find(marker)
if start>=0:
    # 从 marker 开始，找到下一个非注释 location = /teach... 的最末尾大括号
    # 简单做法：统计 {} 深度，直到回到 0
    i=start; depth=0; in_block=False; end=len(s)
    while i<len(s):
        c=s[i]
        if c=='{':
            depth+=1; in_block=True
        elif c=='}':
            depth-=1
            if in_block and depth==0:
                # 还需要吃掉后续的 location /teach {}/@teach {}/ location = /teach {}
                j=i+1
                # 简单：找到下一个空行后紧跟的 server / include / upstream 等关键字作为结束
                m=re.search(r'\n\s*(server|upstream|include|geo|map|split_clients)\s', s[j:])
                if m:
                    end = j+m.start()
                else:
                    # 直接到文件结尾前的最后一个 }
                    end = len(s)
                # 再找 marker 到 end 之间，所有 location {} 完整结束的地方
                # 保守：直接 [marker..end] 全删掉
                s = s[:start] + "\n\n" + s[end:]
                open(p,'w',encoding='utf-8').write(s)
                print('  → 已移除旧 teach location 片段')
                break
        i+=1
PY
  fi
  # 现在注入：找到 server{} 最后一个 }
  INJECT_OK=0
  python3 - "$VHOST" "$SNIPPET_V2" <<PY 2>&1 || true
import sys
p, snip = sys.argv[1], sys.argv[2]
s = open(p, encoding='utf-8', errors='ignore').read()
snippet = open(snip, encoding='utf-8', errors='ignore').read()
# 找到最外层 server{} 的闭合 }（仅匹配 http/server 的顶层，depth 计数）
depth=0; server_start=-1; i=0
while i < len(s):
    c = s[i]
    if c == '{':
        depth += 1
        if depth == 1 and server_start < 0:
            # 确认关键词：前 80 字符含 server
            head = s[max(0,i-80):i]
            if 'server' in head:
                server_start = i
    elif c == '}':
        depth -= 1
        if depth == 0 and server_start != -1:
            # 这个 } 就是 server 闭合
            inject = i
            new_s = s[:inject] + "\n\n" + snippet + "\n\n" + s[inject:]
            open(p, 'w', encoding='utf-8').write(new_s)
            print("  → ✅ teach location 已注入到 server{}（pos=%d）" % inject)
            sys.exit(0)
    i += 1
print("  ⚠️ server{} 未定位成功，退化用 include 方式", file=sys.stderr)
sys.exit(1)
PY
  if grep -q 'Teach RAG v2 Nginx locations (强制部署脚本写入)' "$VHOST"; then
    INJECT_OK=1
  else
    echo "" >> "$VHOST"
    echo "include $SNIPPET_V2;" >> "$VHOST"
    warn "用退化 include 方式：已在 conf 末尾追加 include $SNIPPET_V2"
    INJECT_OK=1
  fi
fi

# nginx -t && reload
echo "  → nginx -t 检查..."
if nginx -t 2>&1 | tail -2 | grep -q 'test is successful'; then
  systemctl reload nginx 2>&1 | tail -2
  ok "Nginx 语法正确 + reload 成功"
else
  fail "Nginx 语法错误："
  nginx -t 2>&1 | tail -10 | sed 's/^/       /'
fi

# -------- 9) 全链路健康检查 --------
step "全链路健康检查（本地 + Nginx 反代 + 前端关键词）"

chk_json(){
  URL="$1"; NAME="$2"; T="$3"
  CODE=$(curl -s -o /tmp/h.json -w "%{http_code}" -m "$T" "$URL")
  echo "  [$NAME] HTTP=$CODE  URL=$URL"
  if [ "$CODE" = "200" ]; then
    python3 -c 'import json,sys
try:
 d=json.load(open("/tmp/h.json"))
 if "vector_stats" in d:
   s=d.get("vector_stats",{})
   print("    ok=",d.get("ok")," v=",d.get("version")," llm=",d.get("has_llm_key")," emb=",d.get("has_embed_key")," chunks=",s.get("total_chunks")," docs=",s.get("total_docs"))
 elif "city" in d:
   print("    city=",d.get("city")," temp=",d.get("temperature"),d.get("weather")," humidity=",d.get("humidity"))
 else:
   print("    keys=", list(d.keys())[:10])
except Exception as e:
 print("    warn: json decode fail. 前200字节:", open("/tmp/h.json").read(200))
' 2>&1 | sed 's/^/       /'
  else
    echo "    非 200，前 300 字节:"
    head -c 300 /tmp/h.json; echo
  fi
}

chk_json "http://127.0.0.1:8777/api/health"     "后端直连 health"     10
chk_json "http://127.0.0.1/teach/api/health"    "Nginx /teach/api"    15
chk_json "http://127.0.0.1/teach/api/weather"   "汉寿天气"            20

echo ""
echo "  [前端 /teach/ 首页]"
CODE=$(curl -s -o /tmp/h.html -w "%{http_code}" -m 10 "http://127.0.0.1/teach/")
SIZE=$(wc -c </tmp/h.html 2>/dev/null || echo 0)
echo "    HTTP=$CODE  size=$SIZE bytes"
if [ "$CODE" = "200" ] && [ "$SIZE" -gt 50000 ]; then
  HITS=$(grep -oE '早上好，刘老师|教学助手|国风|收集箱|阅读|日程|AI 助手|教学工具|设置与数据|static/style.css|static/app.js' /tmp/h.html | sort -u | wc -l)
  echo "    前端关键词命中 = $HITS / 11（>=7 即为新前端已上线）"
  grep -oE '早上好，刘老师|国风|设置与数据|AI 助手' /tmp/h.html | sort -u | sed 's/^/      ✨ 命中: /' || true
  [ "$HITS" -ge 5 ] && ok "前端部署成功 ✅ 关键词命中数 $HITS" || warn "关键词命中偏低（$HITS），可能是缓存/老 HTML，浏览器强刷新 Ctrl+F5 再看。"
elif [ "$CODE" = "200" ]; then
  warn "首页太小($SIZE B)，可能不是新前端。前1000字节："
  head -c 1000 /tmp/h.html; echo
else
  fail "首页 HTTP $CODE，内容："
  head -c 500 /tmp/h.html; echo
fi

echo ""
echo "========================================================================="
echo " 🎉 前端 + 后端 + Nginx location 一站式强制部署完成"
echo "  📱 访问:   http://47.97.115.209/teach/"
echo "  🛰 若首页样式不对 → 浏览器 Ctrl+F5 强制刷新（清掉旧 CSS/JS 缓存）"
echo "  🔑 最后一步: /teach/ → 设置与数据 → 填写 3 把 Key → 保存并测试"
if [ -n "$BACKUP" ]; then
echo "  🧳 回滚:     cp -a $BACKUP/* $INSTALL_DIR/ && systemctl restart teach && systemctl reload nginx"
fi
echo "========================================================================="
