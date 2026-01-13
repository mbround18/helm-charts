#!/usr/bin/env python3
"""
Generate a charts table and inject into docs/README.md between markers.

Usage: python3 tools/update_readme_charts.py docs/README.md

This scans the `charts/` directory, skips charts whose Chart.yaml has
`type: library`, and produces a markdown table with columns:
- Chart (name/link)
- Version
- Setup (HTML `<details>` with first paragraph of chart README if present)
- Values (helm show values command)

It replaces the region between `## CHARTS:START` and `## CHARTS:END`.
"""

import os
import sys
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def first_paragraph(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                # return first non-empty paragraph (stop at blank line)
                para = [s]
                for line2 in f:
                    if not line2.strip():
                        break
                    para.append(line2.rstrip())
                return "\n".join(para)
    return ""


def read_chart_yaml(chart_dir):
    path = os.path.join(chart_dir, "Chart.yaml")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except Exception:
            return None


def build_table(charts_root="charts"):
    rows = []
    for name in sorted(os.listdir(charts_root)):
        chart_dir = os.path.join(charts_root, name)
        if not os.path.isdir(chart_dir):
            continue
        meta = read_chart_yaml(chart_dir)
        if not meta:
            continue
        if meta.get("type") == "library":
            continue
        chart_name = meta.get("name") or name
        version = meta.get("version", "-")
        # chart link: link to the chart's README.md (relative to docs/ directory)
        readme_path = f"../charts/{name}/README.md"
        chart_link = f'<a href="{readme_path}">' + escape_html(chart_name) + "</a>"
        # produce install and values shell commands (inline code)
        install_cmd = f"helm install {name} mbround18/{name} --namespace {name} --create-namespace"
        values_cmd = f"helm show values mbround18/{name}"
        rows.append((chart_link, version, install_cmd, values_cmd))
    # build HTML table
    lines = []
    lines.append("<table>")
    lines.append("  <thead>")
    lines.append(
        "    <tr><th>name</th><th>version</th><th>setup</th><th>values</th></tr>"
    )
    lines.append("  </thead>")
    lines.append("  <tbody>")
    for c, v, install_cmd, values_cmd in rows:
        install_html = (
            '<pre><code class="language-sh">'
            + escape_html(install_cmd)
            + "</code></pre>"
        )
        values_html = (
            '<pre><code class="language-sh">'
            + escape_html(values_cmd)
            + "</code></pre>"
        )
        lines.append(
            f"    <tr><td>{c}</td><td>{v}</td><td>{install_html}</td><td>{values_html}</td></tr>"
        )
    lines.append("  </tbody>")
    lines.append("</table>")
    return "\n".join(lines)


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inject_readme(readme_path):
    start_marker = "<!-- CHARTS:START -->"
    end_marker = "<!-- CHARTS:END -->"
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    if start_marker not in content or end_marker not in content:
        print(
            f"Markers not found in {readme_path}. Add '{start_marker}' and '{end_marker}' to the file."
        )
        return 1
    before, rest = content.split(start_marker, 1)
    _, after = rest.split(end_marker, 1)
    repo_block = (
        "```bash\n"
        + "helm repo add mbround18 https://mbround18.github.io/helm-charts/\n"
        + "helm repo update\n"
        + "```"
    )
    table = build_table(os.path.join(ROOT, "charts"))
    new = (
        before
        + start_marker
        + "\n\n"
        + repo_block
        + "\n\n"
        + table
        + "\n\n"
        + end_marker
        + after
    )
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Updated charts table in {readme_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tools/update_readme_charts.py docs/README.md")
        sys.exit(2)
    path = sys.argv[1]
    sys.exit(inject_readme(path))
