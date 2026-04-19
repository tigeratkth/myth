"""直接用 LiteLLM 测试火山方舟 API Key 的连通性。"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

key = os.getenv("VOLCENGINE_API_KEY", "")
print(f"[info] VOLCENGINE_API_KEY 读取到: {'yes' if key else 'no'}  末4位={key[-4:] if key else ''}")
print(f"[info] VOLCENGINE_API_BASE = {os.getenv('VOLCENGINE_API_BASE') or '(默认 https://ark.cn-beijing.volces.com/api/v3)'}")

# LiteLLM 对 Volcengine 的 API 兼容层期望标准请求；我们挨个试几种候选模型名
CANDIDATES = [
    "volcengine/doubao-1-5-pro-32k",
    "volcengine/doubao-pro-32k",
    "volcengine/doubao-lite-32k",
]

# 若用户传进来一个 endpoint_id（ep-xxx 形式），也一起测
endpoint_env = os.getenv("VOLCENGINE_ENDPOINT_ID", "").strip()
if endpoint_env:
    CANDIDATES.insert(0, f"volcengine/{endpoint_env}")

from litellm import completion  # type: ignore

for model in CANDIDATES:
    print(f"\n=== 测试模型: {model} ===")
    t0 = time.time()
    try:
        resp = completion(
            model=model,
            messages=[{"role": "user", "content": "你好，请用一句话自我介绍。"}],
            temperature=0.0,
            max_tokens=64,
            timeout=20,
        )
        dt = int((time.time() - t0) * 1000)
        text = ""
        try:
            text = resp.choices[0].message.content or ""
        except Exception:
            text = str(resp)[:200]
        print(f"[OK] 用时 {dt}ms  响应: {text.strip()[:120]}")
    except Exception as e:
        dt = int((time.time() - t0) * 1000)
        msg = str(e).replace("\n", " ")[:400]
        print(f"[FAIL] 用时 {dt}ms  error: {msg}")
