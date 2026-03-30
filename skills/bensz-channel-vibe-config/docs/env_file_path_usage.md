# BdcEnv.env_file_path 使用示例

## 作用

`BdcEnv.env_file_path` 记录“本次实际使用的 `.env` 文件路径”。如果配置直接来自 OS 环境变量，则它是 `None`。

它的用途只有两个：
- 调试时快速确认配置来源
- 日志里明确写出实际用了哪个 `.env`

## 最小用法

```python
from _bdc_env import resolve_bdc_env
from pathlib import Path

env = resolve_bdc_env(skill_root=Path('.'))

print(f"URL: {env.url}")
print(f"KEY: {env.key_prefix()}")
print(f"配置文件: {env.env_file_path}")
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

```python
@dataclass(frozen=True)
class BdcEnv:
    url: str
    key: str
    url_source: EnvSource
    key_source: EnvSource
    env_file_path: Path | None
```

`resolve_bdc_env()` 在查找配置时，会把真正命中的 `.env` 路径记到 `env_file_path`：

```python
def resolve_bdc_env(*, skill_root: Path, env_file: Path | None = None) -> BdcEnv:
    ...
    return BdcEnv(..., env_file_path=used_env_file)
```

## 最佳实践

- 调试配置问题时，先看 `env_file_path`
- 测试环境优先用 `--env`
- 生产环境优先用 OS 环境变量，避免配置文件泄露
- 做敏感写操作前，若 `env_file_path is None`，最好再确认当前 shell 环境是否正确

## 相关命令

`env_check.py` 会显示实际使用的 `.env` 文件路径：

```bash
python3 scripts/env_check.py
============================================================
bensz-channel-vibe-config 环境配置检查
============================================================

✓ URL: http://localhost:6542
  来源: cwd_env → BENSZ_CHANNEL_URL (/path/to/.env)

✓ KEY: bdc_e3auGpHp…
  来源: cwd_env → BENSZ_CHANNEL_KEY (/path/to/.env)

✓ 使用的 .env 文件: /path/to/.env
```

`client.py` 会自动复用 `resolve_bdc_env()` 找到的配置：

```bash
python3 scripts/client.py channels list
python3 scripts/client.py --env /path/to/test.env channels list
```
