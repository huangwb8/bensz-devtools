# BdcEnv.env_file_path 使用示例

## 概述

从 v1.0.2 开始，`BdcEnv` 数据类新增了 `env_file_path` 字段，用于记录实际使用的 .env 文件路径。这个改进确保工作函数能够明确知道配置来源，便于调试和日志记录。

## 使用场景

### 1. 调试配置来源

当配置出现问题时，可以快速定位配置文件：

```python
from _bdc_env import resolve_bdc_env
from pathlib import Path

env = resolve_bdc_env(skill_root=Path('.'))

print(f"URL: {env.url}")
print(f"KEY: {env.key_prefix()}")
print(f"配置文件: {env.env_file_path}")
```

输出示例：
```
URL: http://localhost:6542
KEY: bdc_e3auGpHp…
配置文件: /Volumes/2T01/Github/bensz-channel/.env
```

### 2. 日志记录

在工作函数中记录配置来源，便于追踪问题：

```python
def cmd_channels_list(env: BdcEnv, timeout_seconds: int) -> int:
    if env.env_file_path:
        print(f"[DEBUG] 使用配置文件: {env.env_file_path}")
    else:
        print(f"[DEBUG] 使用环境变量或默认配置")

    # 执行实际操作
    res = _call("GET", _url(env, "/api/vibe/channels"), ...)
    return 0 if res.status == 200 else 1
```

### 3. 配置验证

在执行敏感操作前，验证配置来源：

```python
def cmd_channels_delete(env: BdcEnv, timeout_seconds: int, channel_id: str) -> int:
    # 如果配置来自环境变量（没有 .env 文件），可能需要额外确认
    if env.env_file_path is None:
        print("⚠️  警告：配置来自环境变量，请确认操作环境正确")

    # 执行删除操作
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/channels/{channel_id}"), ...)
        return 0 if res.status == 200 else 1
```

## 配置优先级

`env_file_path` 的值取决于配置来源的优先级：

| 优先级 | 配置来源 | env_file_path 值 |
|--------|---------|------------------|
| 1 | OS 环境变量 | `None` |
| 2 | 用户指定的 --env | 指定的文件路径 |
| 3 | 当前目录及父目录的 .env | 找到的第一个 .env 文件路径 |
| 4 | 用户主目录配置文件 | fallback 配置文件路径 |

## 实现细节

### BdcEnv 数据类

```python
@dataclass(frozen=True)
class BdcEnv:
    url: str
    key: str
    url_source: EnvSource
    key_source: EnvSource
    env_file_path: Path | None  # 新增字段
```

### resolve_bdc_env() 函数

在查找配置时，会记录实际使用的 .env 文件路径：

```python
def resolve_bdc_env(*, skill_root: Path, env_file: Path | None = None) -> BdcEnv:
    # ...
    used_env_file: Path | None = None  # 记录实际使用的 .env 文件路径

    for src, env, file_path in sources:
        if key_value is None:
            k, v = _first_present(env, key_keys)
            if v is not None:
                key_value = v
                if src.kind in {"env_file", "cwd_env", "fallback_env"}:
                    if used_env_file is None and file_path is not None:
                        used_env_file = file_path

    return BdcEnv(url=url, key=key, url_source=url_source,
                  key_source=key_source, env_file_path=used_env_file)
```

## 最佳实践

1. **调试时优先检查 env_file_path**：当配置出现问题时，首先检查 `env_file_path` 确认配置来源
2. **日志中记录配置来源**：在关键操作的日志中记录 `env_file_path`，便于追踪问题
3. **测试时使用 --env**：在测试环境中使用 `--env` 参数指定测试配置文件
4. **生产环境使用环境变量**：在生产环境中优先使用 OS 环境变量，避免配置文件泄露

## 相关命令

### env_check.py

现在会显示实际使用的 .env 文件路径：

```bash
$ python3 scripts/env_check.py
============================================================
bensz-channel-vibe-config 环境配置检查
============================================================

✓ URL: http://localhost:6542
  来源: cwd_env → BENSZ_CHANNEL_URL (/path/to/.env)

✓ KEY: bdc_e3auGpHp…
  来源: cwd_env → BENSZ_CHANNEL_KEY (/path/to/.env)

✓ 使用的 .env 文件: /path/to/.env
```

### client.py

所有命令都会自动使用 `env_file_path` 中记录的配置：

```bash
# 使用默认配置（自动查找 .env）
$ python3 scripts/client.py channels list

# 使用指定的 .env 文件
$ python3 scripts/client.py --env /path/to/test.env channels list
```
