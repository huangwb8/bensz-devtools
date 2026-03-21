from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _vibe_env import resolve_vibe_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DUDU_VIBE_URL + DUDU_VIBE_KEY without leaking secrets.")
    parser.add_argument("--env-file", type=str, default=None, help="Optional path to .env file.")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parents[1]
    env_file = Path(args.env_file).expanduser() if args.env_file else None
    vibe = resolve_vibe_env(skill_root=skill_root, env_file=env_file)

    problems: list[str] = []
    if not vibe.url:
        problems.append("缺少 URL：请设置 DUDU_VIBE_URL（或 dudu_vibe_url / dudu_base_url）")
    if not vibe.key:
        problems.append("缺少 KEY：请设置 DUDU_VIBE_KEY（或 dudu_vibe_key / dudu_vibe_api）")
    if vibe.key and len(vibe.key) < 16:
        problems.append("KEY 长度不足（需要 >= 16）")

    print("dudu-vibe-config env check")
    print(f"- url: {vibe.url} (source={vibe.url_source.kind}:{vibe.url_source.detail})")
    print(f"- key: {vibe.key_prefix()} (source={vibe.key_source.kind}:{vibe.key_source.detail})")

    if problems:
        print("\n问题：")
        for p in problems:
            print(f"- {p}")
        return 2

    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
