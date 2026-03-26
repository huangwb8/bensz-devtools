from __future__ import annotations

import argparse
import json
from pathlib import Path

from _local_derive import RUNNER_CHOICES, derive_locally


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="local_derive.py",
        description="Use local AI (codex/claude CLI) to build derivedQuery + derivedPlan without relying on dudu server-side AI.",
    )
    parser.add_argument("--prompt", required=True, help="Topic/subscription prompt to derive locally.")
    parser.add_argument("--topic-name", default=None, help="Optional topic name for disambiguation.")
    parser.add_argument("--runner", default="auto", choices=RUNNER_CHOICES)
    parser.add_argument("--model", default=None, help="Optional local runner model override.")
    parser.add_argument("--effort", default=None, help="Optional local runner effort/reasoning setting.")
    parser.add_argument("--timeout", type=int, default=180, help="Local runner timeout seconds.")
    parser.add_argument("--output", default=None, help="Optional path to write the JSON result.")
    args = parser.parse_args(argv)

    result = derive_locally(
        prompt=args.prompt,
        topic_name=args.topic_name,
        runner=args.runner,
        model=args.model,
        effort=args.effort,
        timeout_seconds=int(args.timeout),
    )
    payload = {
        "runner": result.runner,
        "derivedQuery": result.derived_query,
        "derivedPlan": result.derived_plan,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
