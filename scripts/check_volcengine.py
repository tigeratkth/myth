"""一次性验证：火山方舟新增是否正确接入。"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

# 1. 语法
for f in ["app.py", "pages/4_settings.py", "src/llm.py", "src/config_utils.py"]:
    ast.parse(Path(f).read_text(encoding="utf-8"))
print("[1] SYNTAX OK")

# 2. config.yaml 内容
cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
volc = [m for m in cfg["models"] if m["provider"] == "volcengine"]
assert len(volc) >= 1, "config.yaml 缺少 volcengine 模型"
print(f"[2] config.yaml volcengine 模型数: {len(volc)}")
for m in volc:
    flag = "enabled" if m["enabled"] else "disabled"
    print(f"    - {m['id']:<40s}  {m['display_name']:<22s}  {flag}")

# 3. llm._PROVIDER_ENV_KEY
from src.llm import _PROVIDER_ENV_KEY, list_models
assert "volcengine" in _PROVIDER_ENV_KEY, "llm.py 未注册 volcengine"
print(f"[3] _PROVIDER_ENV_KEY[volcengine] = {_PROVIDER_ENV_KEY['volcengine']}")

# 4. list_models 能正常返回
enabled = [m for m in list_models(only_enabled=True) if m["provider"] == "volcengine"]
print(f"[4] list_models 启用的火山方舟模型: {len(enabled)} 个")
for m in enabled:
    print(f"    > {m['display_name']:<22s}  env_key={m['env_key']:<22s}  configured={m['env_configured']}")

# 5. config_utils 显示名 + env_status
from src.config_utils import _PROVIDER_DISPLAY, env_status
assert _PROVIDER_DISPLAY["volcengine"] == "火山方舟"
es = env_status()
print(f"[5] env_status total_providers = {es['api_keys']['total_providers']}")
assert es["api_keys"]["total_providers"] == 5, f"应有 5 家 Provider，实际 {es['api_keys']['total_providers']}"

# 6. settings 页面 PROVIDERS 列表也包含 volcengine
import importlib.util
spec = importlib.util.spec_from_file_location("settings_page", "pages/4_settings.py")
src = Path("pages/4_settings.py").read_text(encoding="utf-8")
assert "volcengine" in src and "VOLCENGINE_API_KEY" in src and "火山方舟" in src
print("[6] settings 页面 PROVIDERS 已含 volcengine")

# 7. .env.example
ev = Path(".env.example").read_text(encoding="utf-8")
assert "VOLCENGINE_API_KEY" in ev and "VOLCENGINE_API_BASE" in ev
print("[7] .env.example 含 VOLCENGINE_API_KEY / VOLCENGINE_API_BASE")

# 8. README
rd = Path("README.md").read_text(encoding="utf-8")
assert "VOLCENGINE_API_KEY" in rd and "火山方舟" in rd and "doubao" in rd
print("[8] README 已记录火山方舟")

print("\n[OK] 火山方舟接入验证通过")
