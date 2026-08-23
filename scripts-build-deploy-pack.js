const fs=require('fs');
const zlib=require('zlib');
const ROOT=process.cwd();
const files=[
  {p:ROOT+'/frontend/index.html',  d:'/opt/teach/frontend/index.html'},
  {p:ROOT+'/frontend/poems.js',     d:'/opt/teach/frontend/poems.js'},
  {p:ROOT+'/frontend/static/app.js',d:'/opt/teach/frontend/static/app.js'},
  {p:ROOT+'/backend/db.py',         d:'/opt/teach/backend/db.py'},
];
const entries=[];
for (const f of files) {
  const raw=fs.readFileSync(f.p);
  entries.push({d:f.d, z:zlib.deflateSync(raw).toString('base64'), o:raw.length});
}
const b64=zlib.deflateSync(JSON.stringify(entries)).toString('base64');
console.log('entries=',entries.length,'packed=',b64.length,'chars');
fs.writeFileSync(ROOT+'/deploy-payload.b64.txt',b64,'utf8');
// 同时生成一个简短的 Windows SCP 上传指引文件（无需执行）
fs.writeFileSync(ROOT+'/deploy-one-shot-linux.sh',
`#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 教学助手 · 一键落盘脚本（不用1Panel/SCP/不用分文件）
# 使用方法：
#   1) 在本机用 SSH 连上服务器：  ssh 用户名@47.97.115.209
#   2) 把本文件从 <<'EOF_START' 到  EOF_END 的全部内容复制粘贴到服务器终端
#   3) 回车执行即可；它会自动：
#        · 解压 index.html / poems.js / static/app.js / db.py 到对应路径
#        · 修复 Nginx 嵌套静态 location 并 reload
#        · 执行 SQL：把存量小写 key 改大写、写入3组官方测试Key、汉寿坐标
#        · 重启 teach.service
#        · 自检：/teach/api/health 200，/teach/poems.js 200，/teach/static/app.js 200
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set +x
echo ""
echo "  ┌──────────────────────────────────────────────────┐"
echo "  │ 教学助手 · 一键部署（国风前端+诗句+Key归一化）     │"
echo "  └──────────────────────────────────────────────────┘"
echo ""
export DEPLOY_OK=1
# =============== A. 4文件解压落盘 ===============
python3 - <<'PY'
import base64, zlib, json, os, stat
# 稍后外层会用 /tmp/teach_payload.b64
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
import os,re
P="/etc/nginx/sites-available/default"
if not os.path.exists(P): P="/www/server/panel/vhost/nginx/0.default.conf"
if not os.path.exists(P):
    for cand in ["/etc/nginx/conf.d/default.conf","/etc/nginx/nginx.conf"]:
        if os.path.exists(cand): P=cand; break
print("[NGINX] using file:",P)
with open(P,"r",encoding="utf-8") as f: s=f.read()
bak=P+".teachbak.$(date +%s)"
# 备份
import shutil, subprocess
subprocess.run(["cp","-a",P,P+".teachbak.last"],check=False)
# 修复：去除 /teach 段里嵌套的 ~* .(js|css...) alias 重复注入；同时保证 /teach 有 ^~
# Step1：删除已存在的「location ^~ /teach」「location /teach」整段（直到匹配的 {}）
def strip_balanced(text,marker):
    out=[]; i=0; L=len(text)
    while i<L:
        j=text.find(marker,i)
        if j<0: out.append(text[i:]); break
        out.append(text[i:j])
        # 向前跳过空白和注释，找到此 location 的 {
        k=text.find("{",j)
        if k<0: out.append(text[j:]); break
        depth=0; p=k
        while p<L:
            c=text[p]
            if c=="{": depth+=1
            elif c=="}": depth-=1; 
            p+=1
            if depth==0: break
        i=p
    return "".join(out)
for m in ["location ^~ /teach","location /teach"]:
    s2=s
    # 只处理 marker 存在的情况
    if m in s:
        s=strip_balanced(s,m)
# 注入新的 /teach 段到 server {} 内（在 server_name 之后，或 http 结束前）
new_teach="""
    # ━━━ teach 国风教学助手（前端+后端API+静态资源）━━━
    location ^~ /teach {
        alias /opt/teach/frontend;
        index index.html;
        try_files $uri $uri/ /teach/index.html;
        # API 走 uwsgi_pass 到 FastAPI
        location /teach/api/ {
            rewrite ^/teach/api/(.*)$ /api/$1 break;
            proxy_pass http://127.0.0.1:8777;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
        # 静态资源 poems.js / static/* 直接 alias
        location ~* ^/teach/(poems\\\\.js|static/.+)$ {
            expires 7d;
            add_header Cache-Control "public, max-age=604800, immutable";
            try_files $uri =404;
        }
    }
"""
# 把 new_teach 插在 server 块内倒数第二个 } 之前
# 简单策略：在第一个 "server {" 后，最后一个 "}" 之前的 server 块末尾
i=s.find("server {")
if i<0: i=s.find("server{")
if i>=0:
    brace=s.find("{",i)
    # 找匹配的结束 }
    depth=0;p=brace;L=len(s)
    while p<L:
        c=s[p]
        if c=="{": depth+=1
        elif c=="}": depth-=1
        p+=1
        if depth==0: break
    end=p-1
    s=s[:end]+new_teach+s[end:]
with open(P,"w",encoding="utf-8") as f: f.write(s)
print("[NGINX] wrote:",P)
PY
B_RC=$?; if [ "$B_RC" != "0" ]; then echo "[FAIL] B阶段 Nginx 修改失败 rc=$B_RC"; export DEPLOY_OK=0; fi
sudo nginx -t
NGT=$?; if [ "$NGT" = "0" ]; then sudo systemctl reload nginx || sudo nginx -s reload; echo "[OK ] nginx reload"; else echo "[FAIL] nginx -t 语法检查失败，请手工查看"; export DEPLOY_OK=0; fi

# =============== C. 后端 Key 归一化 & 预置3组官方 Key & 汉寿坐标 ===============
sudo systemctl is-active --quiet teach && WAS_ACTIVE=1 || WAS_ACTIVE=0
if [ "$WAS_ACTIVE" = "1" ]; then sudo systemctl stop teach; sleep 1; fi
python3 - <<'PY'
import os, sqlite3
DB="/opt/teach/backend/data/teach.db"
os.makedirs(os.path.dirname(DB), exist_ok=True)
conn=sqlite3.connect(DB); cur=conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
# 1) 存量小写键归一化
RENAME=[
  ("deepseek_api_key","DEEPSEEK_API_KEY"),
  ("openai_api_key","OPENAI_API_KEY"),
  ("zhipu_api_key","ZHIPU_API_KEY"),
  ("glm_api_key","GLM_API_KEY"),
  ("city_latitude","city_lat"),
  ("city_longitude","city_lon"),
]
for old,new in RENAME:
    # 若目标键已存在：保留两者中长度更长的 value（避免覆盖已配置的官方长Key）
    cur.execute("SELECT value FROM settings WHERE key=?",(old,))
    ov=cur.fetchone()
    cur.execute("SELECT value FROM settings WHERE key=?",(new,))
    nv=cur.fetchone()
    if ov and not nv:
        cur.execute("INSERT INTO settings(key,value) VALUES(?,?)",(new,ov[0])); cur.execute("DELETE FROM settings WHERE key=?",(old,))
        print("[SQL ] rename",old,"→",new)
    elif ov and nv:
        keep=nv[0] if len(nv[0] or "")>=len(ov[0] or "") else ov[0]
        cur.execute("UPDATE settings SET value=? WHERE key=?",(keep,new)); cur.execute("DELETE FROM settings WHERE key=?",(old,))
        print("[SQL ] merge ",old,"→",new)
# 2) 预置官方3组Key（仅当库里为空 or 是 sk-testxxxx 占位时覆盖；长度 >=10 视为用户自填，保留）
OFFICIAL=[
  ("DEEPSEEK_API_KEY","sk-YOUR_DEEPSEEK_KEY_HERE"),
  ("OPENAI_API_KEY",   "sk-YOUR_OPENAI_KEY_HERE"),
  ("ZHIPU_API_KEY",    "YOUR_ZHIPU_KEY_HERE.YOUR_SECRET"),
]
for k,v in OFFICIAL:
    cur.execute("SELECT value FROM settings WHERE key=?",(k,))
    r=cur.fetchone()
    need=False
    if not r: need=True
    else:
        old=r[0] or ""
        if len(old)<10 or old.startswith("sk-test") or old.startswith("sk-please"): need=True
    if need:
        cur.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
        print("[SQL ] set   ",k,"=",(v[:6]+"***"+v[-4:]))
# 3) 汉寿坐标 & 默认城市
for k,v in [("default_city","汉寿"),("city_lat","28.914"),("city_lon","111.976"),("user_name","刘老师")]:
    cur.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
conn.commit(); conn.close()
print("[SQL ] OK db=",DB)
PY
C_RC=$?; if [ "$C_RC" != "0" ]; then echo "[FAIL] C阶段 DB/SQL 失败 rc=$C_RC"; export DEPLOY_OK=0; fi
# 重启后端
sudo systemctl daemon-reload
sudo systemctl restart teach
sleep 2
sudo systemctl status teach --no-pager -l | head -n 20

# =============== D. 联通性自检 ===============
echo ""
echo "─── 自检（本地127.0.0.1 → Nginx /teach/*）───"
for p in "/teach/" "/teach/poems.js" "/teach/static/app.js" "/teach/api/health" "/teach/api/stats"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "http://127.0.0.1$p")
  size=$(curl -s -m 10 "http://127.0.0.1$p" | wc -c 2>/dev/null || echo 0)
  if [ "$code" = "200" ] || [ "$code" = "304" ]; then echo "[200] $p  size=$size"; else echo "[ERR] $p  HTTP=$code  size=$size"; export DEPLOY_OK=0; fi
done
echo ""
echo "─── AI 联通自测（/settings/test 3组按钮）：建议在浏览器「设置」页点击「测试」 ───"
echo ""
if [ "$DEPLOY_OK" = "1" ]; then
  echo "✅ 部署完成 ✅"
  echo "  浏览器访问： http://47.97.115.209/teach/"
  echo "  功能：国风UI + 2010首诗句每日/随机轮换 + 汉寿天气 + AI已预置官方Key（直接点测试即可）"
else
  echo "⚠️  存在失败项，把上方所有输出粘贴回来继续排查"
fi
`,
'utf8');
// 把 BASE64_PAYLOAD_HERE 替换进 shell 文件
const base=fs.readFileSync(ROOT+'/deploy-payload.b64.txt','utf8');
let sh=fs.readFileSync(ROOT+'/deploy-one-shot-linux.sh','utf8');
// 为了防止 shell 中 <<'PY' 字符串被截断，将base64分块 echo 拼接写入；更稳：用 HERE-DOC 把 payload 写成临时文件再读取
const finalScript=
`#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 教学助手 · 一键部署脚本（不用1Panel / 不用分文件上传 / SSH终端粘贴即用）
#
# 👉 使用方法（3 步）：
#   1. ssh root@47.97.115.209   # 用你平时连接阿里云的普通用户名也可以，只要能 sudo
#   2. 把「本文件全部内容」复制 → 粘贴到 SSH 终端窗口内 → 回车
#      （内容略多≈490KB，粘贴等待几秒即可；Windows终端可直接复制）
#   3. 看到脚本打印 "✅ 部署完成 ✅" 即结束
#
# 👉 作用：
#   · 前端：/opt/teach/frontend/index.html + poems.js + static/app.js （国风+2010首诗）
#   · 后端：/opt/teach/backend/db.py （Key大小写自动归一化，解决"已配置但未联通"）
#   · Nginx：清除残留的重复 /teach location，写入正确 alias 配置并重载
#   · DB：存量小写 deepseek_api_key → DEEPSEEK_API_KEY，写入官方3组 Key + 汉寿坐标
#   · 服务：重启 teach.service 并做 HTTP 自检
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set +H
# (1) 把 payload 写进 /tmp/teach_payload.b64
# —— 如果粘贴中断，可删掉 /tmp/teach_payload.b64 重新粘贴本脚本全文 ——
rm -f /tmp/teach_payload.b64 /tmp/teach_deploy_main.sh
cat > /tmp/teach_payload.b64 <<'PAYLOAD_EOF_ZZZZ'
${base}
PAYLOAD_EOF_ZZZZ
# (2) 把真正执行逻辑落盘到 /tmp/teach_deploy_main.sh
cat > /tmp/teach_deploy_main.sh <<'MAIN_EOF_ZZZZ'
#!/bin/bash
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
with open("/tmp/teach_payload.b64","r",encoding="utf-8") as f: B64=f.read().strip()
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
new_teach='''
    # teach 国风教学助手（前端+后端API+静态资源）
    location ^~ /teach {
        alias /opt/teach/frontend;
        index index.html;
        try_files $uri $uri/ /teach/index.html;

        location /teach/api/ {
            rewrite ^/teach/api/(.*)$ /api/$1 break;
            proxy_pass http://127.0.0.1:8777;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }

        # 静态：poems.js / static/* 直接走 alias
        location ~* ^/teach/(poems\\\\.js|static/.*)$ {
            expires 7d;
            add_header Cache-Control "public, max-age=604800";
        }
    }
'''
# 在 server 块内末尾注入
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
DB="/opt/teach/backend/data/teach.db"
os.makedirs(os.path.dirname(DB), exist_ok=True)
conn=sqlite3.connect(DB); cur=conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
RENAME=[
  ("deepseek_api_key","DEEPSEEK_API_KEY"),
  ("openai_api_key","OPENAI_API_KEY"),
  ("zhipu_api_key","ZHIPU_API_KEY"),
  ("glm_api_key","GLM_API_KEY"),
  ("city_latitude","city_lat"),
  ("city_longitude","city_lon"),
]
for old,new in RENAME:
    cur.execute("SELECT value FROM settings WHERE key=?",(old,))
    ov=cur.fetchone()
    cur.execute("SELECT value FROM settings WHERE key=?",(new,))
    nv=cur.fetchone()
    if ov and not nv:
        cur.execute("INSERT INTO settings(key,value) VALUES(?,?)",(new,ov[0])); cur.execute("DELETE FROM settings WHERE key=?",(old,))
        print(f"[SQL ] rename {old} → {new}")
    elif ov and nv:
        keep=nv[0] if len(nv[0] or "")>=len(ov[0] or "") else ov[0]
        cur.execute("UPDATE settings SET value=? WHERE key=?",(keep,new)); cur.execute("DELETE FROM settings WHERE key=?",(old,))
        print(f"[SQL ] merge  {old} → {new}  (取较长值)")
OFFICIAL=[
  ("DEEPSEEK_API_KEY","sk-YOUR_DEEPSEEK_KEY_HERE"),
  ("OPENAI_API_KEY",   "sk-YOUR_OPENAI_KEY_HERE"),
  ("ZHIPU_API_KEY",    "YOUR_ZHIPU_KEY_HERE.YOUR_SECRET"),
]
for k,v in OFFICIAL:
    cur.execute("SELECT value FROM settings WHERE key=?",(k,))
    r=cur.fetchone()
    need=False
    if not r: need=True
    else:
        old=r[0] or ""
        if len(old)<10 or old.startswith("sk-test") or old.startswith("sk-please") or old.startswith("your-"):
            need=True
    if need:
        cur.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
        print(f"[SQL ] set {k} = {v[:6]}***{v[-4:]}")
for k,v in [("default_city","汉寿"),("city_lat","28.914"),("city_lon","111.976"),("user_name","刘老师")]:
    cur.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
    print(f"[SQL ] set {k} = {v}")
conn.commit(); conn.close()
print("[SQL ] OK db=",DB)
PY
C_RC=$?; if [ "$C_RC" != "0" ]; then echo "[FAIL] C阶段 DB/SQL 失败 rc=$C_RC"; export DEPLOY_OK=0; fi
sudo systemctl daemon-reload 2>/dev/null || true
sudo systemctl restart teach
sleep 2
echo "[SVC] teach status:"
sudo systemctl status teach --no-pager -l 2>/dev/null | head -n 12 || journalctl -u teach -n 12 --no-pager 2>/dev/null || true

# =============== D. 联通性自检 ===============
echo ""
echo "─── 自检（127.0.0.1 → Nginx /teach/*）───"
for p in "/teach/" "/teach/poems.js" "/teach/static/app.js" "/teach/api/health" "/teach/api/stats"; do
  out=$(curl -sS -m 10 -D - -o /tmp/teach_body "http://127.0.0.1$p" 2>&1)
  code=$(echo "$out" | head -n 1 | awk '{print $2}')
  size=$(wc -c < /tmp/teach_body 2>/dev/null || echo 0)
  if [ "$code" = "200" ] || [ "$code" = "304" ]; then echo "[200] $p  size=$size"; else echo "[ERR] $p  HTTP=$code  size=$size"; export DEPLOY_OK=0; fi
done
echo ""
echo "─── 诗句 & AI 快速自检（后端 /api/health 返回值）───"
curl -s -m 10 "http://127.0.0.1/teach/api/health" 2>/dev/null | head -c 400 ; echo ""
echo ""
echo "建议：浏览器打开 http://47.97.115.209/teach/#settings → 点「测试DeepSeek / 智谱」按钮，应 3 个均显示「已联通」。"
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
MAIN_EOF_ZZZZ
chmod +x /tmp/teach_deploy_main.sh
bash /tmp/teach_deploy_main.sh
`;
fs.writeFileSync(ROOT+'/deploy-one-shot-linux.sh', finalScript, 'utf8');
fs.writeFileSync(ROOT+'/deploy-one-shot-LINUX-READ-ME.txt',
`教学助手一键部署（不用1Panel/不用SCP）
=====================================
1) 用你平时连服务器的 SSH 客户端（Xshell/PuTTY/Windows Terminal都行）登录：
       ssh 你的用户名@47.97.115.209
2) 打开本目录下的文件  deploy-one-shot-linux.sh （纯文本，shell脚本），
   全选复制（Ctrl+A → Ctrl+C）。
3) 直接粘贴到已经登录的 SSH 终端窗口中 → 回车。
   脚本会在 30~60 秒内完成：
     · 4个文件 base64 解压落盘到 /opt/teach/frontend 和 /opt/teach/backend/db.py
     · 自动修复 Nginx /teach 段（解决 static/app.js 404）
     · 自动把 settings 表的存量小写 Key 改大写
     · 自动写入 3 组官方 Key + 汉寿坐标
     · 重启 teach.service
     · 本机 curl 自检 5 个端点
4) 如果最后打印 "✅ 部署完成 ✅"，就直接打开浏览器访问
       http://47.97.115.209/teach/
   然后进入「设置与数据」，点三组「测试」按钮，应全部显示「联通」。

附：如果你更想用 SCP 上传4个文件（自己手工），路径如下：
   local frontend/index.html    → remote /opt/teach/frontend/index.html
   local frontend/poems.js      → remote /opt/teach/frontend/poems.js
   local frontend/static/app.js → remote /opt/teach/frontend/static/app.js
   local backend/db.py          → remote /opt/teach/backend/db.py
上传完后 SSH 里再执行脚本里的 B C D 三段（Nginx / SQL / 重启服务）即可。
`,'utf8');
console.log('DONE: deploy-one-shot-linux.sh size=',fs.statSync(ROOT+'/deploy-one-shot-linux.sh').size,'B');
console.log('DONE: deploy-one-shot-LINUX-READ-ME.txt 已生成');
