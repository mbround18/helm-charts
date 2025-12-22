#!/usr/bin/env python3
"""Split a helm template output into files under a target directory.

Usage: split_manifests.py INPUT_FILE OUT_DIR

It looks for a line starting with `# Source: ` and strips the leading
"<chart>/templates/" prefix to derive the output path. Falls back to
numbered files when no source comment is present.
"""

import os
import sys


def write_doc(out_dir, src_path, doc, idx):
    if src_path:
        # strip leading chart/templates/
        parts = src_path.split("/templates/", 1)
        target = parts[1] if len(parts) == 2 else src_path
        out_path = os.path.join(out_dir, target)
    else:
        out_path = os.path.join(out_dir, f"manifest-{idx:02d}.yaml")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(doc)


def main():
    if len(sys.argv) != 3:
        print("Usage: split_manifests.py INPUT_FILE OUT_DIR", file=sys.stderr)
        sys.exit(2)

    inp, out_dir = sys.argv[1], sys.argv[2]
    if inp == "-":
        content = sys.stdin.read()
    else:
        with open(inp, "r") as f:
            content = f.read()

    docs = []
    # Split on lines that are exactly '---' (YAML document separator)
    parts = []
    cur = []
    for line in content.splitlines(keepends=True):
        if line.strip() == "---":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(line)
    parts.append("".join(cur))

    idx = 0
    for part in parts:
        if not part.strip():
            continue
        src = None
        for ln in part.splitlines():
            if ln.startswith("# Source:"):
                src = ln[len("# Source:") :].strip()
                break
        write_doc(out_dir, src, part, idx)
        idx += 1


if __name__ == "__main__":
    main()
