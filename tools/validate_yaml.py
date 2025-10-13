#!/usr/bin/env python3
import sys
import os
from typing import List

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required. Install dependencies with 'uv sync' or run via 'uv run'.",
        file=sys.stderr,
    )
    raise


def find_yaml_files(root: str) -> List[str]:
    exts = {".yml", ".yaml"}
    found = []
    for base, _, files in os.walk(root):
        for name in files:
            _, ext = os.path.splitext(name)
            if ext.lower() in exts:
                found.append(os.path.join(base, name))
    return sorted(found)


def validate_yaml(files: List[str]) -> int:
    errors = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                # Load all documents in a multi-doc YAML file
                for _ in yaml.safe_load_all(fh):
                    pass
        except Exception as e:
            errors += 1
            print(f"YAML error in {f}: {e}", file=sys.stderr)
    return errors


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "./tmp"
    files = find_yaml_files(root)
    if not files:
        print(
            f"No YAML files found under {root} (did you run 'make dump'?).",
            file=sys.stderr,
        )
        return 2
    errs = validate_yaml(files)
    if errs:
        print(f"Validation failed: {errs} file(s) had YAML errors.")
        return 1
    print(f"Validation passed: {len(files)} file(s) are valid YAML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
