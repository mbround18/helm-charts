#!/usr/bin/env python3
import sys
import argparse
import yaml
from pathlib import Path


def validate_stream(stream: str, source: str) -> int:
    try:
        # Helm templates can include multiple YAML documents separated by '---'.
        docs = list(yaml.safe_load_all(stream))
        # Make sure at least one non-empty doc exists
        if not any(doc is not None for doc in docs):
            print(
                f"WARN: {source}: No YAML documents found (or all empty).",
                file=sys.stderr,
            )
        return 0
    except yaml.YAMLError as e:
        print(f"ERROR: {source}: YAML parsing failed: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Validate Helm templated YAML output")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a YAML file to validate; if omitted, reads stdin",
    )
    args = parser.parse_args()

    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            return 2
        content = p.read_text(encoding="utf-8")
        return validate_stream(content, str(p))
    else:
        content = sys.stdin.read()
        return validate_stream(content, "<stdin>")


if __name__ == "__main__":
    sys.exit(main())
