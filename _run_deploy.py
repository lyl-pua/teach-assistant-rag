"""paramiko 上传 teach-v2.tar.gz 并远程执行 deploy.sh
非交互式：密码硬编码从环境变量 DEPLOY_SSH_PWD 读取，或本文件直接传参。
"""
import os, sys, time

HOST = "47.97.115.209"
USER = "root"
PWD  = os.environ.get("DEPLOY_SSH_PWD") or sys.argv[1]

LOCAL_TAR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teach-v2.tar.gz")
REMOTE_TAR = "/root/teach-v2.tar.gz"
DEPLOY_CMD = (
    "set -euo pipefail; "
    "rm -rf /opt/teach-upgrade; "
    "mkdir -p /opt/teach-upgrade; "
    "tar -xzf /root/teach-v2.tar.gz -C /opt/teach-upgrade; "
    "bash /opt/teach-upgrade/deploy.sh 2>&1 | tee /opt/teach-upgrade/deploy.last.log; "
    "echo =====SUMMARY=====; "
    "tail -n 30 /opt/teach-upgrade/deploy.last.log"
)

import paramiko

def log(*a): print("[DEPLOY]", *a, flush=True)

def main():
    if not PWD:
        print("需要通过环境变量 DEPLOY_SSH_PWD 或第一个参数提供 SSH 密码")
        sys.exit(1)
    if not os.path.exists(LOCAL_TAR):
        print(f"找不到本地 tar 包: {LOCAL_TAR}")
        sys.exit(1)

    size_mb = os.path.getsize(LOCAL_TAR) / 1024 / 1024
    log(f"tar 包: {LOCAL_TAR}  ({size_mb:.2f} MB)")
    log(f"连接 SSH: {USER}@{HOST} ...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PWD, timeout=20, banner_timeout=20, auth_timeout=20)

    # SFTP 上传（显示进度）
    log(f"[1/3] SFTP 上传 {LOCAL_TAR}  ->  {USER}@{HOST}:{REMOTE_TAR}")
    sftp = ssh.open_sftp()
    file_size = os.path.getsize(LOCAL_TAR)
    uploaded = 0
    last_tick = [time.time(), 0]
    def cb(transferred, total):
        now = time.time()
        if now - last_tick[0] >= 2.0 or transferred == total:
            speed_kb = (transferred - last_tick[1]) / (now - last_tick[0]) / 1024
            pct = transferred / total * 100 if total else 0
            print(f"    进度 {transferred//1024}KB / {total//1024}KB  {pct:5.1f}%   {speed_kb:.0f} KB/s", flush=True)
            last_tick[0] = now; last_tick[1] = transferred
    sftp.put(LOCAL_TAR, REMOTE_TAR, callback=cb if size_mb > 0.5 else None)
    sftp.chmod(REMOTE_TAR, 0o644)
    remote_stat = sftp.stat(REMOTE_TAR)
    sftp.close()
    log(f"上传完成: 远端大小 {remote_stat.st_size} B")

    # 远程执行
    log("[2/3] 远端执行 deploy.sh (最长 480 秒)...")
    log("-" * 64)
    transport = ssh.get_transport()
    chan = transport.open_session(timeout=None)
    chan.settimeout(None)
    chan.set_combine_stderr(True)
    chan.exec_command(DEPLOY_CMD)
    # 读取输出
    buf = bytearray()
    while True:
        try:
            data = chan.recv(4096)
        except Exception:
            data = b""
        if not data:
            if chan.exit_status_ready():
                break
            time.sleep(0.1)
            continue
        sys.stdout.buffer.write(data); sys.stdout.buffer.flush()
        buf.extend(data)
    exit_code = chan.recv_exit_status()
    log("-" * 64)
    log(f"[3/3] 远程脚本 exit_code = {exit_code}")
    ssh.close()

    # 快速 HTTP 健康检查
    import urllib.request
    health_url = f"http://{HOST}/teach/api/health"
    try:
        with urllib.request.urlopen(health_url, timeout=15) as resp:
            body = resp.read().decode("utf-8", "replace")
            log(f"外网健康检查 HTTP {resp.status}: {body[:200]}")
    except Exception as e:
        log(f"外网健康检查失败: {e}")

    if exit_code == 0:
        log("✅ 部署脚本返回 0，浏览器访问 http://47.97.115.209/teach/ 验证")
    else:
        log("⚠️  脚本返回非 0，请把上面所有输出粘贴回来继续排查")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
