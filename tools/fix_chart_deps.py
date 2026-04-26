import sys
import os
import re


def sync_local_dependencies(chart_yaml):
    chart_dir = os.path.dirname(chart_yaml)

    with open(chart_yaml, "r") as f:
        content = f.read()

    # Fast exit if there are no local dependencies
    if "dependencies:" not in content or "file://" not in content:
        return

    # Isolate the dependencies section to avoid mutating other parts of the YAML
    head, tail = content.split("dependencies:", 1)

    # Find the end of the dependencies block (the next unindented key)
    end_match = re.search(r"\n^[a-zA-Z0-9_-]+:", tail, re.MULTILINE)
    if end_match:
        deps_content = tail[: end_match.start()]
        rest_content = tail[end_match.start() :]
    else:
        deps_content = tail
        rest_content = ""

    # Split into individual list items inside dependencies while keeping separators
    items = re.split(r"(\n\s*-\s+)", deps_content)
    changed = False

    # Iterate over the parsed blocks (skipping separators)
    for i in range(2, len(items), 2):
        block = items[i]

        # Look for local file references
        repo_match = re.search(r"repository:\s*file://([^\n]+)", block)
        if repo_match:
            # Clean up the path (strip comments, whitespace, and quotes)
            repo_path = repo_match.group(1).split("#")[0].strip().strip("\"'")
            target_chart = os.path.normpath(
                os.path.join(chart_dir, repo_path, "Chart.yaml")
            )

            if os.path.exists(target_chart):
                with open(target_chart, "r") as tf:
                    # Find the version in the target local chart
                    target_ver_match = re.search(
                        r"^version:\s*([^\n]+)", tf.read(), re.MULTILINE
                    )

                    if target_ver_match:
                        # Clean up target version
                        target_ver = (
                            target_ver_match.group(1).split("#")[0].strip().strip("\"'")
                        )

                        # Replace the version within this specific dependency block
                        new_block = re.sub(
                            r"(version:\s*)[^\n]+",
                            r"\g<1>" + target_ver,
                            block,
                            count=1,
                        )
                        if new_block != block:
                            items[i] = new_block
                            changed = True

    # Save changes back if any alignment occurred
    if changed:
        with open(chart_yaml, "w") as f:
            f.write(head + "dependencies:" + "".join(items) + rest_content)
        print(
            f"    [Sync] Aligned local chart versions in {os.path.basename(chart_dir)}/Chart.yaml"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sync_local_deps.py <path-to-Chart.yaml>")
        sys.exit(1)
    sync_local_dependencies(sys.argv[1])
