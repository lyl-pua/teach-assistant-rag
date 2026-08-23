"""
教学助手一键上传+部署脚本
用法：
  1. 在本地电脑新开一个 PowerShell 窗口
  2. cd 到项目目录
  3. python upload-and-deploy.py
  4. 输入服务器密码（输入时不显示字符，正常现象）
"""
import getpass
import os
import sys
import paramiko

HOST = "47.97.115.209"
USER = "root"
LOCAL_SCRIPT = os.path.join(os.path.dirname(__file__), "deploy-one-shot-linux.sh")
REMOTE_PATH = "/tmp/deploy.sh"

def main():
    print("=" * 56)
    print("  教学助手 · 上传并部署（paramiko SFTP + SSH）")
    print("=" * 56)
    print()

    if not os.path.exists(LOCAL_SCRIPT):
        print(f"[ERROR] 找不到本地文件: {LOCAL_SCRIPT}")
        sys.exit(1)

    size = os.path.getsize(LOCAL_SCRIPT)
    print(f"  本地文件: {LOCAL_SCRIPT}")
    print(f"  大小: {size} B")
    print(f"  目标: {USER}@{HOST}:{REMOTE_PATH}")
    print()

    pwd = getpass.getpass(f"请输入 {USER}@{HOST} 的 SSH 密码: ")

    print()
    print("[1/3] 连接服务器...", end=" ", flush=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, port=22, username=USER, password=pwd, timeout=15)
    except Exception as e:
        print(f"失败: {e}")
        sys.exit(1)
    print("OK")

    print("[2/3] 上传 deploy.sh ...", end=" ", flush=True)
    sftp = ssh.open_sftp()
    sftp.put(LOCAL_SCRIPT, REMOTE_PATH)
    sftp.chmod(REMOTE_PATH, 0o755)
    # 确认大小
    rstat = sftp.stat(REMOTE_PATH)
    print(f"OK ({rstat.st_size} B)")
    sftp.close()

    print("[3/3] 远程执行 bash /tmp/deploy.sh ...")
    print("-" * 56)
    stdin, stdout, stderr = ssh.exec_command("bash /tmp/deploy.sh", timeout=120)
    # 实时打印输出
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="", flush=True)
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        print("--- stderr ---")
        print(err)
    exit_code = stdout.channel.recv_exit_status()
    print("-" * 56)
    print(f"远程执行结束, exit_code={exit_code}")
    ssh.close()
    print()
    if exit_code == 0:
        print("✅ 完成！浏览器打开 http://47.97.115.209/teach/ 验证")
    else:
        print("⚠️  有错误，把上面输出贴回来继续排查")

if __name__ == "__main__":
    main()
