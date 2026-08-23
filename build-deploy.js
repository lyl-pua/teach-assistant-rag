const fs=require('fs');
const zlib=require('zlib');
const ROOT=process.cwd();
const files=[
  {p:ROOT+'/frontend/index.html',  d:'/opt/teach/frontend/index.html'},
  {p:ROOT+'/frontend/poems.js',     d:'/opt/teach/frontend/poems.js'},
  {p:ROOT+'/frontend/static/app.js',d:'/opt/teach/frontend/static/app.js'},
  {p:ROOT+'/frontend/static/style.css', d:'/opt/teach/frontend/static/style.css'},
  {p:ROOT+'/backend/db.py',                    d:'/opt/teach/backend/db.py'},
  {p:ROOT+'/backend/config.py',                d:'/opt/teach/backend/config.py'},
  {p:ROOT+'/backend/rag/generator.py',         d:'/opt/teach/backend/rag/generator.py'},
  {p:ROOT+'/backend/routers/health.py',        d:'/opt/teach/backend/routers/health.py'},
  {p:ROOT+'/backend/routers/settings.py',      d:'/opt/teach/backend/routers/settings.py'},
  {p:ROOT+'/backend/services/weather.py',      d:'/opt/teach/backend/services/weather.py'},
];
const entries=[];
for (const f of files) {
  const raw=fs.readFileSync(f.p);
  entries.push({d:f.d, z:zlib.deflateSync(raw).toString('base64'), o:raw.length});
}
const base=zlib.deflateSync(JSON.stringify(entries)).toString('base64');
console.log('entries=',entries.length,'packed chars=',base.length);
fs.writeFileSync(ROOT+'/deploy-payload.b64.txt',base,'utf8');

// MAIN shell 脚本（不含 payload 段，单独用字符串字面量避免被 HERE-DOC 污染）
const MAIN = String.raw`#!/bin/bash
set +x
echo ""
echo "  ┌──────────────────────────────────────────────────┐"
echo "  │ 教学助手 · 一键部署（国风前端+诗句+Key归一化）     │"
echo "  └──────────────────────────────────────────────────┘"
echo ""
export DEPLOY_OK=1
# =============== A. 4文件解压落盘 ===============
python3 - <<'PY'
import base64, zlib, json, os
P="/tmp/teach_payload.b64"
with open(P,"r",encoding="utf-8") as f: B64=f.read().strip()
try:
    arr=json.loads(zlib.decompress(base64.b64decode(B64)).decode("utf-8"))
except Exception as e:
    print("[FAIL] payload decode error:",e); raise SystemExit(1)
for e in arr:
    dst=e["d"]
    raw=zlib.decompress(base64.b64decode(e["z"]))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst,"wb") as f: f.write(raw)
    os.chmod(dst, 0o644)
    print("[OK ] write",dst,"  size=",len(raw),"B  orig=",e["o"])
PY
A_RC=$?; if [ "$A_RC" != "0" ]; then echo "[FAIL] A阶段 写入文件失败 rc=$A_RC"; export DEPLOY_OK=0; fi

# =============== B. Nginx 静态资源修复 ===============
python3 - <<'PY'
import os, subprocess
P="/etc/nginx/sites-available/default"
candidates=["/etc/nginx/sites-available/default","/www/server/panel/vhost/nginx/0.default.conf","/www/server/panel/vhost/nginx/default.conf","/etc/nginx/conf.d/default.conf"]
for cand in candidates:
    if os.path.exists(cand):
        P=cand; break
print("[NGINX] using file:",P)
subprocess.run(["cp","-a",P,P+".teachbak.last"],check=False)
with open(P,"r",encoding="utf-8") as f: s=f.read()
def strip_balanced(text,marker):
    out=[]; i=0; L=len(text)
    while i<L:
        j=text.find(marker,i)
        if j<0: out.append(text[i:]); break
        out.append(text[i:j])
        k=text.find("{",j)
        if k<0: out.append(text[j:]); break
        depth=0; p=k
        while p<L:
            c=text[p]
            if c=="{": depth+=1
            elif c=="}": depth-=1
            p+=1
            if depth==0: break
        i=p
    return "".join(out)
for m in ["location ^~ /teach","location /teach"]:
    if m in s: s=strip_balanced(s,m)
new_teach="""
    # teach 国风教学助手
    # ---------- (1) 所有 /teach/api/* 请求 → 直接代理 FastAPI（最高优先级，绝对不 fallback 到 index.html）----------
    location ^~ /teach/api/ {
        rewrite ^/teach/api/(.*)$ /api/$1 break;
        proxy_pass http://127.0.0.1:8777;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
    }

    # ---------- (2) /teach/ 下静态资源 ----------
    location ^~ /teach/ {
        alias /opt/teach/frontend/;
        index index.html;
        # 注意：location 带尾部斜杠 + alias 带尾部斜杠，请求 /teach/x/y 会映射为 /opt/teach/frontend/x/y（不会重复拼接 /teach）
        # 前端路由 fallback：仅当 URI 不是真实文件/目录时，才回退到 index.html（HTML5 History SPA）
        try_files $uri $uri/ /teach/index.html;
    }
"""
idx=s.find("server {")
if idx<0: idx=s.find("server{")
if idx>=0:
    brace=s.find("{",idx)
    depth=0; p=brace; L=len(s)
    while p<L:
        c=s[p]
        if c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0:
                s=s[:p]+new_teach+s[p:]
                break
        p+=1
with open(P,"w",encoding="utf-8") as f: f.write(s)
print("[NGINX] wrote:",P)
PY
B_RC=$?; if [ "$B_RC" != "0" ]; then echo "[FAIL] B阶段 Nginx 修改失败 rc=$B_RC"; export DEPLOY_OK=0; fi
sudo nginx -t
NGT=$?
if [ "$NGT" = "0" ]; then
  sudo systemctl reload nginx >/dev/null 2>&1 || sudo nginx -s reload >/dev/null 2>&1 || true
  echo "[OK ] nginx reload"
else
  echo "[FAIL] nginx -t 语法检查失败，请把错误贴出来继续排查"
  export DEPLOY_OK=0
fi

# =============== C. 后端 Key 归一化 & 预置3组官方 Key & 汉寿坐标 ===============
sudo systemctl is-active --quiet teach && WAS_ACTIVE=1 || WAS_ACTIVE=0
if [ "$WAS_ACTIVE" = "1" ]; then sudo systemctl stop teach 2>/dev/null; sleep 1; fi
python3 - <<'PY'
import os, sqlite3

# ⚠️ 这里必须与 config.py 的 DB_PATH 保持完全一致：/opt/teach/backend/data/app.db
# （之前版本误写成 teach.db，导致"写入A库但后端读B库，Key长度永远0"的死局）
DB_MAIN = "/opt/teach/backend/data/app.db"
DB_OLD = "/opt/teach/backend/data/teach.db"  # v1/v2 误写入的老库，需要合并

os.makedirs(os.path.dirname(DB_MAIN), exist_ok=True)

def _open(path):
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    return c

# 1) 打开主库 app.db，确保 settings 表结构完整（老表缺列必须 ALTER TABLE 补，CREATE TABLE IF NOT EXISTS 不补列！）
m = _open(DB_MAIN)
mc = m.cursor()
mc.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
# 查列名
mc.execute("PRAGMA table_info(settings)")
cols = { (str(r[1] or "")).lower() for r in mc.fetchall() }
NEED = {"key","value","updated_at"}
for col in sorted(NEED - cols):
    if col == "updated_at":
        try:
            mc.execute("ALTER TABLE settings ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print(f"[SQL ] ALTER 补列 updated_at 成功")
        except Exception as e:
            print(f"[SQL ] ALTER 补列 updated_at 失败（继续但不写此列）: {e}")
    # key/value 理论上不可能缺，万一缺不硬加避免 PRIMARY KEY 冲突

# 安全 upsert：老表没 updated_at 列就回退到双列版
def safe_upsert(cur, key, value):
    # 先试带 updated_at 的 3 列版
    sql_v3 = "INSERT INTO settings(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP"
    sql_v2 = "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    try:
        cur.execute(sql_v3, (key, value))
        return "v3"
    except Exception:
        try:
            cur.execute(sql_v2, (key, value))
            return "v2"
        except Exception as e2:
            raise RuntimeError(f"safe_upsert {key} 两版都失败: {e2}")

# 安全 UPDATE set xxx = excluded.value, updated_at=... 同样提供 fallback
def safe_update_kv(cur, key, value):
    try:
        cur.execute("UPDATE settings SET value=?, updated_at=CURRENT_TIMESTAMP WHERE key=?", (value, key))
        return "v3"
    except Exception:
        cur.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
        return "v2"

# 2) 如果老库 teach.db 存在且有 settings 表 → 把里面记录合并进主库（取较长值/覆盖空值）
if os.path.exists(DB_OLD):
    try:
        o = _open(DB_OLD)
        oc = o.cursor()
        oc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if oc.fetchone():
            oc.execute("SELECT key,value FROM settings")
            rows = oc.fetchall()
            merged = 0
            for r in rows:
                ok, ov = (r["key"] or "").strip(), (r["value"] if r["value"] is not None else "")
                if not ok: continue
                mc.execute("SELECT value FROM settings WHERE key=?", (ok,))
                cur = mc.fetchone()
                cv = (cur[0] if (cur and cur[0] is not None) else "")
                # 取非空 + 较长值
                if (not cv) or len(ov) > len(cv):
                    if cur:
                        safe_update_kv(mc, ok, ov)
                    else:
                        safe_upsert(mc, ok, ov)
                    merged += 1
            o.close()
            print(f"[SQL ] 合并老库 {DB_OLD} 到 {DB_MAIN}，迁移记录数={merged}")
    except Exception as e:
        print(f"[SQL ] 合并老库失败（忽略继续）: {e}")

RENAME=[
  ("deepseek_api_key","DEEPSEEK_API_KEY"),
  ("openai_api_key","OPENAI_API_KEY"),
  ("zhipu_api_key","ZHIPU_API_KEY"),
  ("glm_api_key","GLM_API_KEY"),
  ("city_latitude","city_lat"),
  ("city_longitude","city_lon"),
]
for old,new in RENAME:
    mc.execute("SELECT value FROM settings WHERE key=?",(old,))
    ov=mc.fetchone()
    mc.execute("SELECT value FROM settings WHERE key=?",(new,))
    nv=mc.fetchone()
    if ov and not nv:
        safe_upsert(mc, new, ov[0]); mc.execute("DELETE FROM settings WHERE key=?",(old,))
        print(f"[SQL ] rename {old} -> {new}")
    elif ov and nv:
        ovv = ov[0] or ""; nvv = nv[0] or ""
        keep = nvv if len(nvv) >= len(ovv) else ovv
        safe_update_kv(mc, new, keep); mc.execute("DELETE FROM settings WHERE key=?",(old,))
        print(f"[SQL ] merge  {old} -> {new}  (取较长值 len={len(keep)})")

OFFICIAL=[
  ("DEEPSEEK_API_KEY","sk-YOUR_DEEPSEEK_KEY_HERE"),
  ("OPENAI_API_KEY",   "sk-YOUR_OPENAI_KEY_HERE"),
  ("ZHIPU_API_KEY",    "YOUR_ZHIPU_KEY_HERE.YOUR_SECRET"),
]

for k,v in OFFICIAL:
    mc.execute("SELECT value FROM settings WHERE key=?",(k,))
    r=mc.fetchone()
    cur_v = (r[0] if r else None) or ""
    need = False
    if not r or not cur_v:
        need = True
    else:
        # 值太短 / 明显占位符 / DeepSeek/智谱格式不对
        if len(cur_v) < 10:
            need = True
        elif cur_v.startswith(("sk-test","sk-please","your-","xxxx","****","demo-","please-")):
            need = True
        elif k.endswith("_API_KEY") and k.startswith(("DEEPSEEK_","OPENAI_")) and (not cur_v.startswith("sk-")):
            need = True
        elif k == "ZHIPU_API_KEY" and "." not in cur_v and len(cur_v) < 20:
            need = True
    if need:
        safe_upsert(mc, k, v)
        print(f"[SQL ] set {k} = {v[:6]}***{v[-4:]}  (覆盖原长度={len(cur_v)})")
    else:
        print(f"[SQL ] keep {k} (现有长度={len(cur_v)}，不覆盖)")

for k,v in [("default_city","汉寿"),("city_lat","28.914"),("city_lon","111.976"),("user_name","刘老师")]:
    safe_upsert(mc, k, v)
    print(f"[SQL ] set {k} = {v}")

# 3) 写完后打印一次最终长度，方便肉眼确认：有长度 > 30 说明 Key 真的写入 app.db 了
print("[SQL ] - 写入后主库校验：")
for chk in ["DEEPSEEK_API_KEY","OPENAI_API_KEY","ZHIPU_API_KEY"]:
    mc.execute("SELECT value FROM settings WHERE key=?",(chk,))
    rr = mc.fetchone()
    vv = rr[0] if rr else ""
    print(f"[SQL ]   {chk}: len={len(vv)}  tail={vv[-6:] if vv else '(空)'}")

m.commit(); m.close()
print(f"[SQL ] OK 写入主库 db={DB_MAIN}")
PY
C_RC=$?; if [ "$C_RC" != "0" ]; then echo "[FAIL] C阶段 DB/SQL 失败 rc=$C_RC"; export DEPLOY_OK=0; fi
sudo systemctl daemon-reload 2>/dev/null || true
sudo systemctl restart teach
sleep 2
echo "[SVC] teach status:"
sudo systemctl status teach --no-pager -l 2>/dev/null | head -n 12 || journalctl -u teach -n 12 --no-pager 2>/dev/null || true

# =============== D. 联通性自检 ===============
echo ""
echo "--- 自检（127.0.0.1 -> Nginx /teach/*）---"
for p in "/teach/" "/teach/poems.js" "/teach/static/app.js" "/teach/api/health" "/teach/api/stats" "/teach/api/weather" "/teach/api/settings"; do
  out=$(curl -sS -m 10 -D - -o /tmp/teach_body "http://127.0.0.1$p" 2>&1)
  code=$(echo "$out" | head -n 1 | awk '{print $2}')
  size=$(wc -c < /tmp/teach_body 2>/dev/null || echo 0)
  ct=$(echo "$out" | grep -iE '^content-type:' | head -n 1 | sed 's/\r//g')
  if [ "$code" = "200" ] || [ "$code" = "304" ]; then
    echo "[200] $p  size=$size  $ct"
  else
    echo "[ERR] $p  HTTP=$code  size=$size"; export DEPLOY_OK=0
  fi
done
echo ""
echo "--- 诗句 & AI 快速自检（后端 /api/health 返回值）---"
curl -s -m 10 "http://127.0.0.1/teach/api/health" 2>/dev/null | head -c 500 ; echo ""
echo ""
echo "--- 3 个官方 Key 联通性（后端直连：DeepSeek chat / 智谱 chat / 智谱 embedding）---"
echo "[1/3] POST /teach/api/settings/test-llm {provider=deepseek}"
DS_R=$(curl -s -m 60 -X POST "http://127.0.0.1/teach/api/settings/test-llm" -H "Content-Type: application/json" -d '{"provider":"deepseek"}' 2>/dev/null)
echo "      -> $DS_R"
echo "$DS_R" | grep -q '"success":\s*true' || export DEPLOY_OK=0
echo "[2/3] POST /teach/api/settings/test-llm {provider=zhipu}"
ZP_R=$(curl -s -m 60 -X POST "http://127.0.0.1/teach/api/settings/test-llm" -H "Content-Type: application/json" -d '{"provider":"zhipu"}' 2>/dev/null)
echo "      -> $ZP_R"
echo "$ZP_R" | grep -q '"success":\s*true' || export DEPLOY_OK=0
echo "[3/3] POST /teach/api/settings/test-embed"
EM_R=$(curl -s -m 60 -X POST "http://127.0.0.1/teach/api/settings/test-embed" -H "Content-Type: application/json" -d '{}' 2>/dev/null)
echo "      -> $EM_R"
echo "$EM_R" | grep -q '"success":\s*true' || export DEPLOY_OK=0
echo ""
echo "建议：浏览器打开 http://47.97.115.209/teach/#settings -> 点 3 个「测试」按钮，应全显示「已联通」。"
if [ "$DEPLOY_OK" = "1" ]; then
  echo ""
  echo "✅ 部署完成 ✅"
  echo "  · 国风前端：已加载"
  echo "  · 诗句：poems.js 共 2010 首；每日稳定1首 / 刷新天气再换1首 / 点诗句块随机换"
  echo "  · AI Key：官方三组已预置（DeepSeek / OpenAI / 智谱 GLM），设置页直接点测试"
  echo "  · 天气：已固定为 汉寿（28.914, 111.976）每天更新"
  echo "  · Key归一化：前端无论保存小写/大写 Key，后端 db.py 都会自动映射大写，解决「已配置但未联通」"
else
  echo ""
  echo "⚠️  有失败项，请把整段终端输出粘贴回来，我继续修"
fi
`;

// 组装最终脚本（不能使用模板字符串插值 `${base}` 会被 HERE-DOC 影响；我们直接字符串拼接）
let final = "";
final += '#!/bin/bash\n';
final += '# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
final += '# 教学助手 · 一键部署脚本（不用1Panel / 不用分文件上传 / SSH终端粘贴即用）\n';
final += '#\n';
final += '# 👉 使用方法（3 步）：\n';
final += '#   1. ssh root@47.97.115.209   # 用你平时连接阿里云的普通用户名也可以，只要能 sudo\n';
final += '#   2. 打开本脚本，全部复制（Ctrl+A → Ctrl+C），粘贴进 SSH 终端窗口里，回车。\n';
final += '#      （内容约 145KB，粘贴等待几秒即可。）\n';
final += '#   3. 看到最后打印 "✅ 部署完成 ✅" 就完成了。\n';
final += '# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
final += 'set +H\n';
final += 'rm -f /tmp/teach_payload.b64 /tmp/teach_deploy_main.sh\n';
final += "cat > /tmp/teach_payload.b64 <<'PAYLOAD_EOF_ZZZZ'\n";
final += base + '\n';
final += 'PAYLOAD_EOF_ZZZZ\n';
final += "cat > /tmp/teach_deploy_main.sh <<'MAIN_EOF_ZZZZ'\n";
final += MAIN + '\n';
final += 'MAIN_EOF_ZZZZ\n';
final += 'chmod +x /tmp/teach_deploy_main.sh\n';
final += 'bash /tmp/teach_deploy_main.sh\n';

fs.writeFileSync(ROOT+'/deploy-one-shot-linux.sh', final, 'utf8');
fs.writeFileSync(ROOT+'/deploy-one-shot-LINUX-READ-ME.txt',
`教学助手一键部署（不用1Panel/不用SCP/不用分文件上传）
========================================================

用法（复制粘贴进 SSH 终端一次搞定）：

  1) 用你平时的 SSH 方式（Xshell/PuTTY/Windows Terminal 都行）登录服务器
        ssh 你的用户名@47.97.115.209

  2) 在你本地电脑的项目目录里，打开
        deploy-one-shot-linux.sh
     这是一个纯文本文件。全选复制（Ctrl+A → Ctrl+C）。

  3) 直接把内容粘贴进已登录的 SSH 终端窗口 → 回车。
     脚本会在 ~60 秒内自动做完：
        · 4 个文件 base64+deflate 落盘到服务器路径：
             /opt/teach/frontend/index.html
             /opt/teach/frontend/poems.js       （2010首诗句）
             /opt/teach/frontend/static/app.js  （700+首轮换逻辑）
             /opt/teach/backend/db.py           （Key大小写自动归一化）
        · 清理 Nginx 旧/重复 location，重新注入正确 /teach 段并重载
        · DB settings 表：存量小写 Key 改大写；写入官方 3 组 Key + 汉寿坐标
        · 重启 teach.service 并做 5 个 HTTP 端点自检

  4) 脚本结尾打印：
        "✅ 部署完成 ✅"
     然后打开浏览器访问：
        http://47.97.115.209/teach/

  5) 进入「设置与数据」，点三组「测试」按钮，应都显示「已联通」。

如果你更习惯用 SCP 手动上传 4 个文件，路径如下：
  local  frontend/index.html    →  remote /opt/teach/frontend/index.html
  local  frontend/poems.js      →  remote /opt/teach/frontend/poems.js
  local  frontend/static/app.js →  remote /opt/teach/frontend/static/app.js
  local  backend/db.py          →  remote /opt/teach/backend/db.py
上传后回到 SSH 手动执行一次 deploy-one-shot-linux.sh 里 B、C、D 三段即可（Nginx修复 / SQL / 重启服务 / 自检）。

诗句轮换特性：
  · 首次打开首页 / 每天打开 → 按日期哈希稳定取同 1 首
  · 每次天气拉取结束 → 再随机换 1 首
  · 直接点诗句显示的文字块 → 随机换 1 首
`,'utf8');
console.log('OK 打包完成，deploy-one-shot-linux.sh =',final.length,'B');
