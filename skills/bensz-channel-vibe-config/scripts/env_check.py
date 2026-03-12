from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _bdc_env import resolve_bdc_env
from _flat_yaml import load_flat_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 BENSZ_CHANNEL_URL + BENSZ_CHANNEL_KEY 配置（不泄露密钥）。")
    parser.add_argument("--env", type=str, default=None, help="指定 .env 配置文件路径。")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细的搜索路径信息。")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    config = load_flat_yaml(skill_root / "config.yaml")
    env_file = Path(args.env).expanduser() if args.env else None
    env = resolve_bdc_env(skill_root=skill_root, env_file=env_file)

    problems: list[str] = []
    warnings: list[str] = []

    # 验证 URL
    if not env.url:
        problems.append("缺少 URL：请设置 BENSZ_CHANNEL_URL（或 bdc_url）")
    elif not (env.url.startswith("http://") or env.url.startswith("https://")):
        warnings.append(f"URL 格式可能不正确：{env.url}")

    # 验证 KEY
    if not env.key:
        problems.append("缺少 KEY：请设置 BENSZ_CHANNEL_KEY（或 bdc_key）")
    elif len(env.key) < 20:
        problems.append(f"KEY 长度不足（当前 {len(env.key)} 字符，需要 >= 20）")
    elif not env.key.startswith("bdc_"):
        warnings.append("KEY 格式建议：应以 'bdc_' 开头")

    print("=" * 60)
    print("bensz-channel-vibe-config 环境配置检查")
    print("=" * 60)
    print(f"\n✓ URL: {env.url}")
    print(f"  来源: {env.url_source.kind} → {env.url_source.detail}")
    print(f"\n✓ KEY: {env.key_prefix()}")
    print(f"  来源: {env.key_source.kind} → {env.key_source.detail}")
    if env.env_file_path:
        print(f"\n✓ 使用的 .env 文件: {env.env_file_path}")

    if args.verbose:
        print("\n" + "=" * 60)
        print("配置文件搜索路径（按优先级）")
        print("=" * 60)
        print("\n1. OS 环境变量（最高优先级）")
        print("   - 通过 export 命令设置的环境变量")
        print("\n2. 当前工作目录及父目录的 .env 文件")
        candidates = config.lists.get("env_file_candidates", [".env", ".env.local"])
        search_max_depth = int(config.scalars.get("env_search_max_depth", "5"))
        cwd = Path.cwd()
        for _ in range(search_max_depth):
            for candidate in candidates:
                print(f"   - {cwd / candidate}")
            parent = cwd.parent
            if parent == cwd:
                break
            cwd = parent
        print("\n3. 用户主目录配置文件（fallback）")
        print("   - ~/.bensz-channel.env")
        print("   - ~/.config/bensz-channel/devtools.env")

    if warnings:
        print("\n" + "=" * 60)
        print("⚠️  警告")
        print("=" * 60)
        for w in warnings:
            print(f"  • {w}")

    if problems:
        print("\n" + "=" * 60)
        print("❌ 配置问题")
        print("=" * 60)
        for p in problems:
            print(f"  • {p}")

        print("\n" + "=" * 60)
        print("💡 配置指南")
        print("=" * 60)
        print("\n方式 1：在当前目录创建 .env 文件")
        print("  $ cat > .env << 'EOF'")
        print("  BENSZ_CHANNEL_URL=http://localhost:6542")
        print("  BENSZ_CHANNEL_KEY=bdc_your_api_key_here")
        print("  EOF")
        print("\n方式 2：设置环境变量")
        print("  $ export BENSZ_CHANNEL_URL=http://localhost:6542")
        print("  $ export BENSZ_CHANNEL_KEY=bdc_your_api_key_here")
        print("\n方式 3：在用户主目录创建全局配置")
        print("  $ cat > ~/.bensz-channel.env << 'EOF'")
        print("  BENSZ_CHANNEL_URL=http://localhost:6542")
        print("  BENSZ_CHANNEL_KEY=bdc_your_api_key_here")
        print("  EOF")
        print("\n" + "=" * 60)
        return 2

    print("\n" + "=" * 60)
    print("✅ 配置检查通过")
    print("=" * 60)
    print("\n下一步：运行以下命令验证连接")
    print("  $ python3 scripts/client.py ping")
    print("  $ python3 scripts/client.py doctor")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
