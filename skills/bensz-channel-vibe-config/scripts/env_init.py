#!/usr/bin/env python3
"""
env_init.py - 快速生成 bensz-channel-vibe-config 配置文件

用法：
  python3 scripts/env_init.py                    # 在当前目录创建 .env
  python3 scripts/env_init.py --global           # 在用户主目录创建 ~/.bensz-channel.env
  python3 scripts/env_init.py --path /path/to/.env  # 指定路径
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def generate_env_content(url: str, key: str) -> str:
    """生成 .env 文件内容"""
    return f"""# bensz-channel-vibe-config 配置文件
# 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# bensz-channel 服务器地址
BENSZ_CHANNEL_URL={url}

# DevTools API 密钥（从管理界面生成）
BENSZ_CHANNEL_KEY={key}

# 注意：
# 1. 请勿将此文件提交到版本控制系统（已在 .gitignore 中）
# 2. API 密钥仅在生成时显示一次，请妥善保管
# 3. 如需更换密钥，请在管理界面重新生成
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="快速生成 bensz-channel-vibe-config 配置文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 在当前目录创建 .env
  python3 scripts/env_init.py

  # 在用户主目录创建全局配置
  python3 scripts/env_init.py --global

  # 指定自定义路径
  python3 scripts/env_init.py --path /path/to/.env
        """,
    )
    parser.add_argument(
        "--global",
        dest="use_global",
        action="store_true",
        help="在用户主目录创建 ~/.bensz-channel.env",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="指定配置文件路径",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:6542",
        help="bensz-channel 服务器地址（默认: http://localhost:6542）",
    )
    parser.add_argument(
        "--key",
        type=str,
        default="",
        help="DevTools API 密钥（如不提供，将提示输入）",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="强制覆盖已存在的配置文件",
    )

    args = parser.parse_args()

    # 确定配置文件路径
    if args.path:
        env_path = Path(args.path).expanduser().resolve()
    elif args.use_global:
        env_path = Path.home() / ".bensz-channel.env"
    else:
        env_path = Path.cwd() / ".env"

    # 检查文件是否已存在
    if env_path.exists() and not args.force:
        print(f"❌ 配置文件已存在: {env_path}")
        print("   使用 --force 强制覆盖")
        return 1

    # 获取 API 密钥
    api_key = args.key
    if not api_key:
        print("=" * 60)
        print("bensz-channel-vibe-config 配置向导")
        print("=" * 60)
        print("\n请按照以下步骤获取 API 密钥：")
        print("1. 登录 bensz-channel 管理界面")
        print("2. 进入 [管理员 → DevTools 远程管理]")
        print("3. 点击 [生成新密钥] 并复制（仅显示一次）")
        print()

        try:
            api_key = input("请粘贴 API 密钥: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n已取消")
            return 1

        if not api_key:
            print("❌ API 密钥不能为空")
            return 1

    # 验证 API 密钥格式
    if len(api_key) < 20:
        print(f"⚠️  警告: API 密钥长度不足（当前 {len(api_key)} 字符，建议 >= 20）")
        try:
            confirm = input("是否继续？[y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消")
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\n已取消")
            return 1

    # 生成配置文件
    content = generate_env_content(args.url, api_key)

    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(content, encoding="utf-8")
        env_path.chmod(0o600)  # 设置为仅所有者可读写
    except Exception as e:
        print(f"❌ 创建配置文件失败: {e}")
        return 1

    print("\n" + "=" * 60)
    print("✅ 配置文件创建成功")
    print("=" * 60)
    print(f"\n路径: {env_path}")
    print(f"权限: 600 (仅所有者可读写)")
    print(f"\nURL: {args.url}")
    print(f"KEY: {api_key[:12]}... (已脱敏)")

    print("\n" + "=" * 60)
    print("下一步")
    print("=" * 60)
    print("\n1. 验证配置")
    print("   $ python3 scripts/env_check.py")
    print("\n2. 测试连接")
    print("   $ python3 scripts/client.py ping")
    print("   $ python3 scripts/client.py doctor")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
