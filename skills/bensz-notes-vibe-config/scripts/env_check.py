from __future__ import annotations

import argparse
from pathlib import Path

from _bn_env import resolve_bn_env
from _flat_yaml import load_flat_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 BENSZ_NOTES_URL + BENSZ_NOTES_KEY 配置（不泄露密钥）。")
    parser.add_argument("--env", type=str, default=None, help="指定 .env/remote.env 配置文件路径。")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示搜索路径和 API 前缀。")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    config = load_flat_yaml(skill_root / "config.yaml")
    env = resolve_bn_env(skill_root=skill_root, env_file=Path(args.env).expanduser() if args.env else None)

    problems: list[str] = []
    warnings: list[str] = []
    if not env.url:
        problems.append("缺少 URL：请设置 BENSZ_NOTES_URL。")
    if not env.key:
        problems.append("缺少 KEY：请设置 BENSZ_NOTES_KEY（Agent API Token 或 scoped JWT）。")
    elif len(env.key) < 20:
        problems.append(f"KEY 长度不足（当前 {len(env.key)} 字符，需要 >= 20）。")
    elif not (env.key.startswith("bnt_") or env.key.count(".") == 2):
        warnings.append("KEY 看起来不像 bnt_ API token 或 JWT；如可用可忽略。")

    print("=" * 60)
    print("bensz-notes-vibe-config 环境配置检查")
    print("=" * 60)
    print(f"\nURL: {env.url}")
    print(f"  来源: {env.url_source.kind} -> {env.url_source.detail}")
    print(f"\nAPI prefix: {env.api_prefix or '(empty)'}")
    print(f"  来源: {env.api_prefix_source.kind} -> {env.api_prefix_source.detail}")
    print(f"\nKEY: {env.key_prefix()}")
    print(f"  来源: {env.key_source.kind} -> {env.key_source.detail}")
    if env.env_file_path:
        print(f"\n使用的 env 文件: {env.env_file_path}")

    if args.verbose:
        print("\n" + "=" * 60)
        print("配置搜索路径")
        print("=" * 60)
        print("1. OS 环境变量")
        print("2. 显式 --env 文件")
        print("3. 当前目录向上查找：")
        for name in config.lists.get("env_file_candidates", [".env", ".env.local", "remote.env"]):
            print(f"   - {name}")
        print("4. fallback：")
        for path in config.lists.get("fallback_env_files", []):
            print(f"   - {path}")

    if warnings:
        print("\n警告：")
        for warning in warnings:
            print(f"- {warning}")
    if problems:
        print("\n配置问题：")
        for problem in problems:
            print(f"- {problem}")
        return 2

    print("\n配置检查通过。下一步可运行：")
    print("  python3 scripts/client.py health")
    print("  python3 scripts/client.py doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
