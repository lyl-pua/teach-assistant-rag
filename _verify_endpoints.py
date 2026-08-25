import os, paramiko
HOST = "47.97.115.209"; USER = "root"
PWD = os.environ["DEPLOY_SSH_PWD"]
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PWD, timeout=20, banner_timeout=20, auth_timeout=20)

cmds = [
    ("API /api/tools/list HTTP", "curl -s -m 10 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8777/api/tools/list"),
    ("API /api/settings head", "curl -s -m 10 http://127.0.0.1:8777/api/settings | head -c 240; echo"),
    ("API /api/ai/keys",     "curl -s -m 10 http://127.0.0.1:8777/api/ai/keys | head -c 400; echo"),
    ("工具 /api/tools/generate ppt fallback",
     """curl -s -m 45 -X POST http://127.0.0.1:8777/api/tools/generate \
-H 'Content-Type: application/json' \
-d '{"tool_type":"ppt","subject":"语文","grade":"三年级","unit":"第一单元","topic":"大青树下的小学","extra":"","use_rag":false}' \
| python3 -c 'import sys,json; d=json.load(sys.stdin); slides=d.get("ppt_slides") or d.get("result",{}).get("ppt_slides") or []; print("tool_type=", d.get("tool_type"), "title=", d.get("title")); print("ppt_slides=", len(slides)); [print("  page", s.get("idx"), s.get("title")) for s in slides[:6]]'"""),
]

for label, cmd in cmds:
    print(f"\n===== {label} =====")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out: print(out)
    if err: print("[STDERR]", err[:400])

ssh.close()
