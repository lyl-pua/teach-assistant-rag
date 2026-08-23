# -*- coding: utf-8 -*-
"""
LLM 生成器封装
- 优先 DeepSeek (sk-*)，兜底智谱 glm-4-flash
- 非流式调用
- Token 优化：内存缓存相同 prompt（TTL = config.LLM_CACHE_TTL）
"""
import hashlib
import json
import time
from typing import Optional

import requests

import config

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

ZHIPU_CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4-flash"
ZHIPU_LONG_MODEL = "glm-4"

# 千问 DashScope（多模态：qwen-vl-plus 视觉理解；文本：qwen-plus）
DASHSCOPE_CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DASHSCOPE_VL_MODEL = "qwen-vl-plus"       # 视觉多模态（图文理解）
DASHSCOPE_TEXT_MODEL = "qwen-plus"        # 纯文本生成（兜底）
DASHSCOPE_TTI_MODEL = "wanx-v1"           # 通义万相文本生图（DashScope 官方支持模型名）
# 通义万相 wanx-v1 官方支持的尺寸列表（其他尺寸会触发 InvalidParameter 报错）
#   1024*1024 — 方图（课文配图/插画）
#   720*1280  — 9:16 竖版海报
#   1280*720  — 16:9 横版 PPT 插图
#   1024*1536 — 2:3 竖版
#   1536*1024 — 3:2 横版
WANX_ALLOWED_SIZES = {
    "1024*1024",
    "720*1280",
    "1280*720",
    "1024*1536",
    "1536*1024",
}
WANX_IMAGE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
WANX_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

# =========== Token 优化：LLM 查询缓存 ===========
# 缓存结构：{cache_key: {"content": str, "ts": float, "usage": dict}}
_LLM_CACHE: dict = {}


def _cache_key(prompt: str, system_prompt: Optional[str], model: str) -> str:
    """生成缓存键：prompt + system_prompt + model 的 hash"""
    raw = f"{model}|{system_prompt or ''}|{prompt}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_cached(key: str) -> Optional[dict]:
    """从缓存获取，过期返回 None 并清理"""
    ttl = getattr(config, "LLM_CACHE_TTL", 300)
    item = _LLM_CACHE.get(key)
    if not item:
        return None
    if time.time() - item["ts"] > ttl:
        _LLM_CACHE.pop(key, None)
        return None
    return item


def _set_cached(key: str, content: str, usage: dict) -> None:
    """写入缓存，超过 200 条时清理最旧的"""
    if len(_LLM_CACHE) >= 200:
        # 清理最旧的 50 条
        sorted_keys = sorted(_LLM_CACHE.keys(), key=lambda k: _LLM_CACHE[k]["ts"])
        for k in sorted_keys[:50]:
            _LLM_CACHE.pop(k, None)
    _LLM_CACHE[key] = {"content": content, "ts": time.time(), "usage": usage}


def clear_llm_cache() -> int:
    """清空缓存，返回清理条数"""
    n = len(_LLM_CACHE)
    _LLM_CACHE.clear()
    return n


def get_cache_stats() -> dict:
    """缓存统计"""
    ttl = getattr(config, "LLM_CACHE_TTL", 300)
    now = time.time()
    valid = sum(1 for v in _LLM_CACHE.values() if now - v["ts"] <= ttl)
    return {
        "total_entries": len(_LLM_CACHE),
        "valid_entries": valid,
        "ttl_seconds": ttl,
    }


def _record_token_usage(usage: dict):
    """将每次 LLM 调用的 token 用量写入 DB"""
    import sqlite3
    db_path = config.DB_PATH
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            provider TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms INTEGER
        )
    """)
    cur.execute(
        "INSERT INTO token_usage(ts,provider,model,prompt_tokens,completion_tokens,total_tokens,latency_ms) VALUES(?,?,?,?,?,?,?)",
        (
            usage.get("ts", ""),
            usage.get("provider", ""),
            usage.get("model", ""),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            int(usage.get("total_tokens", 0)),
            int(usage.get("latency_ms", 0)),
        ),
    )
    conn.commit()
    conn.close()


def get_token_stats() -> dict:
    """聚合查询 token 用量统计"""
    import sqlite3
    db_path = config.DB_PATH
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # 总量
    cur.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(prompt_tokens),0) as pt, COALESCE(SUM(completion_tokens),0) as ct, COALESCE(SUM(total_tokens),0) as tt FROM token_usage")
    row = cur.fetchone()
    total = {"calls": row["cnt"], "prompt_tokens": row["pt"], "completion_tokens": row["ct"], "total_tokens": row["tt"]}
    # 按模型分组
    cur.execute("SELECT model, COUNT(*) as cnt, SUM(total_tokens) as tt, SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct FROM token_usage GROUP BY model ORDER BY tt DESC")
    by_model = []
    for r in cur.fetchall():
        by_model.append({"model": r["model"], "calls": r["cnt"], "total_tokens": r["tt"], "prompt_tokens": r["pt"], "completion_tokens": r["ct"]})
    # 最近5条
    cur.execute("SELECT ts,provider,model,prompt_tokens,completion_tokens,total_tokens,latency_ms FROM token_usage ORDER BY id DESC LIMIT 5")
    recent = []
    for r in cur.fetchall():
        recent.append({"ts": r["ts"], "provider": r["provider"], "model": r["model"], "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"], "total_tokens": r["total_tokens"], "latency_ms": r["latency_ms"]})
    conn.close()
    return {"total": total, "by_model": by_model, "recent": recent}


def _provider_info() -> tuple[str, str, str]:
    """返回 (provider, endpoint, model)。优先级：DeepSeek > 智谱 > 千问"""
    sk = config.get_sk_key()
    if sk:
        return "deepseek", DEEPSEEK_URL, DEEPSEEK_MODEL
    zk = config.get_zhipu_key()
    if zk:
        return "zhipu", ZHIPU_CHAT_URL, ZHIPU_MODEL
    dk = config.get_dashscope_key()
    if dk:
        return "dashscope", DASHSCOPE_CHAT_URL, DASHSCOPE_TEXT_MODEL
    raise RuntimeError("未配置任何 LLM API Key（deepseek/openai/zhipu/glm/dashscope/qwen）")


class LLMGenerator:
    """同步 Chat Completions 封装。若未配置 Key，在 chat() 抛异常，由上层降级。"""

    def __init__(self):
        self.last_usage = None  # {"provider":"","model":"","prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"ts":""}

    # 暴露给外面看用的
    def current_provider(self) -> str:
        try:
            return _provider_info()[0]
        except Exception:
            return "none"

    def current_model(self) -> str:
        try:
            return _provider_info()[2]
        except Exception:
            return "none"

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        timeout: int = 120,
        use_cache: bool = True,
    ) -> str:
        provider, endpoint, model = _provider_info()

        # Token 优化：缓存命中检查（仅 temperature 较低时缓存，避免高创造性场景误命中）
        cache_key = None
        if use_cache and temperature <= 0.5:
            cache_key = _cache_key(prompt, system_prompt, model)
            cached = _get_cached(cache_key)
            if cached:
                # 缓存命中：复用 usage（标记为 cached），不调 API
                self.last_usage = dict(cached["usage"])
                self.last_usage["cached"] = True
                return cached["content"]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if provider == "deepseek":
            key = config.get_sk_key()
        elif provider == "zhipu":
            key = config.get_zhipu_key()
        else:
            key = config.get_dashscope_key()
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        t0 = time.time()
        resp = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM {provider} HTTP {resp.status_code} ({time.time()-t0:.1f}s): {resp.text[:300]}"
            )
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"LLM 返回结构异常: {json.dumps(data, ensure_ascii=False)[:300]}") from e

        # 捕获 token 用量
        usage = data.get("usage", {})
        self.last_usage = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": int((time.time() - t0) * 1000),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 持久化到 DB
        try:
            _record_token_usage(self.last_usage)
        except Exception:
            pass

        # Token 优化：写入缓存（仅 temperature 较低时）
        if cache_key:
            _set_cached(cache_key, content, self.last_usage)

        return content or ""

    # ============== 多模态：视觉理解（qwen-vl-plus） ==============
    def vision_chat(
        self,
        image_urls: list[str],
        prompt: str = "请描述这张图片中的内容，并给出小学语文教学场景下可以如何利用这张图。",
        temperature: float = 0.5,
        max_tokens: int = 1500,
        timeout: int = 180,
    ) -> str:
        """
        千问 qwen-vl-plus 视觉问答：接收图片 URL（支持 http(s):// 或 oss://），返回文字理解。
        - 可用于批改作业照片、识别教材页面、理解板书、课堂照片分析等教学场景。
        """
        key = config.get_dashscope_key()
        if not key:
            raise RuntimeError("未配置 DashScope/千问 API Key，无法使用多模态视觉理解（请在设置页填入 DASHSCOPE_API_KEY）")
        if not image_urls:
            raise RuntimeError("至少需要传入一张图片 URL")

        # 构建 qwen-vl-plus 原生 message content 格式
        content = []
        for idx, url in enumerate(image_urls, 1):
            u = (url or "").strip()
            if not u:
                continue
            # 兼容 base64（data:image/...）直接透传；本地文件请先上传再给 URL
            content.append({"image": u})
        content.append({"text": prompt or "请详细描述图片内容。"})
        messages = [{"role": "user", "content": content}]

        body = {
            "model": DASHSCOPE_VL_MODEL,
            "input": {"messages": messages},
            "parameters": {
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
                "result_format": "message",
            },
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        # 同步版：先提交任务，再轮询结果（更稳定，兼容长耗时图片分析）
        submit_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        t0 = time.time()
        resp = requests.post(submit_url, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"qwen-vl-plus 提交失败 HTTP {resp.status_code}: {resp.text[:400]}"
            )
        submit_data = resp.json()
        task_id = submit_data.get("output", {}).get("task_id") or submit_data.get("task_id")
        if not task_id:
            # 兼容同步直接返回（有些版本不需要异步）
            try:
                return submit_data["output"]["choices"][0]["message"]["content"][0]["text"]
            except Exception:
                raise RuntimeError(f"qwen-vl-plus 返回异常: {json.dumps(submit_data, ensure_ascii=False)[:400]}")

        # 轮询任务完成
        task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        poll_headers = {"Authorization": f"Bearer {key}"}
        deadline = time.time() + timeout
        last_body = ""
        while time.time() < deadline:
            time.sleep(2.0)
            r = requests.get(task_url, headers=poll_headers, timeout=30)
            if r.status_code != 200:
                continue
            last_body = r.text
            info = r.json()
            status = (info.get("output", {}).get("task_status") or info.get("task_status") or "").upper()
            if status in {"SUCCEEDED", "SUCCEED", "DONE", "SUCCESS"}:
                try:
                    choices = info["output"]["choices"]
                    ans = choices[0]["message"]["content"]
                    if isinstance(ans, list):
                        texts = [c.get("text", "") for c in ans if isinstance(c, dict)]
                        ans = "\n".join(t for t in texts if t)
                    self.last_usage = {
                        "provider": "dashscope",
                        "model": DASHSCOPE_VL_MODEL,
                        "prompt_tokens": int(info.get("usage", {}).get("input_tokens", 0) or 0),
                        "completion_tokens": int(info.get("usage", {}).get("output_tokens", 0) or 0),
                        "total_tokens": int(info.get("usage", {}).get("image_tokens", 0) or 0)
                                        + int(info.get("usage", {}).get("input_tokens", 0) or 0)
                                        + int(info.get("usage", {}).get("output_tokens", 0) or 0),
                        "latency_ms": int((time.time() - t0) * 1000),
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    try:
                        _record_token_usage(self.last_usage)
                    except Exception:
                        pass
                    return ans or ""
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"qwen-vl-plus 结果结构异常: {json.dumps(info, ensure_ascii=False)[:400]}") from e
            if status in {"FAILED", "FAIL", "ERROR"}:
                raise RuntimeError(f"qwen-vl-plus 任务失败: {json.dumps(info, ensure_ascii=False)[:400]}")
            # RUNNING / PENDING 继续等待
        raise RuntimeError(f"qwen-vl-plus 任务超时: {last_body[:400]}")

    # ============== 多模态：文本生图（通义万相 wanx-v1） ==============
    def text_to_image(
        self,
        prompt: str,
        size: str = "1024*1024",
        n: int = 1,
        timeout: int = 180,
    ) -> list[str]:
        """
        通义万相文生图（走 DashScope Wanx 接口）。返回图片 URL 列表（HTTP 直链，有效期约 1 小时）。
        教学场景：根据课文/古诗词生成配图、教学卡片插画、课堂活动海报等。
        """
        key = config.get_dashscope_key()
        if not key:
            raise RuntimeError("未配置 DashScope/千问 API Key，无法使用文生图（请在设置页填入 DASHSCOPE_API_KEY）")
        if not prompt or not prompt.strip():
            raise RuntimeError("prompt 不能为空")

        # size 白名单校验：wanx-v1 仅接受 1024*1024 / 1024*1536 / 1536*1024
        use_size = (size or "1024*1024").strip().replace("x", "*").replace("×", "*")
        if use_size not in WANX_ALLOWED_SIZES:
            raise RuntimeError(
                f"不支持的文生图尺寸「{size}」，通义万相允许: "
                + ", ".join(sorted(WANX_ALLOWED_SIZES))
            )
        use_n = max(1, min(int(n or 1), 4))

        body = {
            "model": DASHSCOPE_TTI_MODEL,
            "input": {"prompt": prompt.strip()},
            "parameters": {"size": use_size, "n": use_n},
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        t0 = time.time()
        resp = requests.post(WANX_IMAGE_URL, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"万相文生图提交失败 HTTP {resp.status_code}: {resp.text[:400]}"
            )
        info = resp.json()
        task_id = info.get("output", {}).get("task_id") or info.get("task_id")
        if not task_id:
            raise RuntimeError(f"万相文生图未返回任务ID: {json.dumps(info, ensure_ascii=False)[:400]}")

        # 轮询任务完成
        task_url = WANX_TASK_URL.format(task_id=task_id)
        poll_headers = {"Authorization": f"Bearer {key}"}
        deadline = time.time() + timeout
        last_body = ""
        while time.time() < deadline:
            time.sleep(3.0)
            r = requests.get(task_url, headers=poll_headers, timeout=30)
            if r.status_code != 200:
                continue
            last_body = r.text
            info = r.json()
            status = (info.get("output", {}).get("task_status") or info.get("task_status") or "").upper()
            if status in {"SUCCEEDED", "SUCCEED", "DONE", "SUCCESS"}:
                results = info.get("output", {}).get("results") or []
                urls = [it.get("url") or it.get("image_url") for it in results]
                urls = [u for u in urls if u]
                if not urls:
                    raise RuntimeError(f"万相文生图未返回图片: {json.dumps(info, ensure_ascii=False)[:400]}")
                self.last_usage = {
                    "provider": "dashscope",
                    "model": DASHSCOPE_TTI_MODEL,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                return urls
            if status in {"FAILED", "FAIL", "ERROR"}:
                raise RuntimeError(f"万相文生图任务失败: {json.dumps(info, ensure_ascii=False)[:400]}")
        raise RuntimeError(f"万相文生图任务超时: {last_body[:400]}")


# 全局单例
GENERATOR = LLMGenerator()
