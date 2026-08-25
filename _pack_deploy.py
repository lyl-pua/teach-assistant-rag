"""打包升级包 teach-v2.tar.gz（不含用户数据/大体积截图/.git）"""
import os, tarfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "teach-v2.tar.gz")

# 要包含的顶层条目（文件或目录）
INCLUDE = [
    "frontend",
    "backend",
    "requirements.txt",
    "deploy.sh",
    "nginx-teach-location.conf",
]
EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "assets", "docs"}
EXCLUDE_FILES = {".gitignore", "teach-v2.tar.gz", "deploy-payload.b64.txt"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".pyd", ".log", ".db-journal")

def filter_fn(tarinfo: tarfile.TarInfo):
    name = tarinfo.name
    basename = os.path.basename(name)
    # 目录排除
    parts = name.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return None
    if basename in EXCLUDE_FILES:
        return None
    if name.endswith(EXCLUDE_SUFFIX):
        return None
    # 排除 backend/data 下实际用户的 documents 和 app.db/vectorstore.pkl ，
    # deploy.sh 会从原安装目录恢复真实用户数据；保留种子示例文件 .md 没意义，避免覆盖
    if tarinfo.isfile():
        rel = os.path.relpath(name)
        if rel.startswith("backend/data/"):
            # 打包仅保留目录结构，不打包任何真实数据
            return None
    return tarinfo

if os.path.exists(OUT):
    os.remove(OUT)

print(f"[PACK] {OUT}")
with tarfile.open(OUT, "w:gz") as tar:
    for entry in INCLUDE:
        p = os.path.join(ROOT, entry)
        if not os.path.exists(p):
            print(f"  [SKIP] missing: {entry}")
            continue
        tar.add(p, arcname=entry, filter=filter_fn)
        print(f"  [ADD]  {entry}")

size_mb = os.path.getsize(OUT) / 1024 / 1024
print(f"[DONE] {size_mb:.2f} MB -> {OUT}")
