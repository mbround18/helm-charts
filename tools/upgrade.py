import asyncio
import argparse
import datetime
import re
import requests
import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString
from packaging.version import parse as parse_version, InvalidVersion


# --- YAML Loading/Saving Utilities ---
def create_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    return yaml


def load_yaml_file(filepath: Path):
    yaml = create_yaml()
    with open(filepath, "r") as f:
        return yaml.load(f)


def save_yaml_file(filepath: Path, data):
    yaml = create_yaml()
    with open(filepath, "w") as f:
        yaml.dump(data, f)


def apply_scalar_style(new_value: str, existing_value):
    if isinstance(existing_value, DoubleQuotedScalarString):
        return DoubleQuotedScalarString(new_value)
    if isinstance(existing_value, SingleQuotedScalarString):
        return SingleQuotedScalarString(new_value)
    return new_value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Upgrade container image tags in Helm charts."
    )
    parser.add_argument(
        "chart_paths",
        nargs="+",
        type=Path,
        help="Path(s) to Helm chart directories (e.g., charts/my-chart)",
    )
    parser.add_argument(
        "--min-tag-age-days",
        type=int,
        default=14,
        help="Minimum age in days a tag must have to be considered for upgrade (default: 14).",
    )
    parser.add_argument(
        "--chart-concurrency",
        type=int,
        default=4,
        help="Maximum number of charts to process concurrently (default: 4).",
    )
    parser.add_argument(
        "--image-concurrency",
        type=int,
        default=8,
        help="Maximum number of registry lookups to run concurrently (default: 8).",
    )
    return parser.parse_args(argv)


# --- Image Discovery ---
def find_images_in_values(data, path_parts=None):
    if path_parts is None:
        path_parts = []

    images = []

    if isinstance(data, dict) or isinstance(data, CommentedMap):
        # Type 1: Dictionary with separate 'repository' and 'tag' keys
        if "repository" in data and "tag" in data:
            images.append(
                {
                    "path": ".".join(path_parts),
                    "repository_obj": data,  # Reference to the dictionary holding 'repository' and 'tag'
                    "repository_key": "repository",
                    "tag_key": "tag",
                    "current_repository": data["repository"],
                    "current_tag": data["tag"],
                    "type": "repo_tag_keys",
                }
            )

        # Type 2: Key named 'image' (or similar) with a string value like "repo/image:tag"
        for key, value in data.items():
            if isinstance(value, str) and (
                key == "image" or key.endswith("Image")
            ):  # Heuristic for image strings
                full_image_str = value
                repository = full_image_str
                tag = ""

                # Attempt to parse into repository and tag
                if ":" in full_image_str:
                    repository, tag = full_image_str.rsplit(":", 1)

                # Avoid adding duplicates if already caught by Type 1 (e.g. `image: {repository: foo, tag: bar}`)
                # This might happen if 'image' is a sub-key of a larger image object
                if "repository" not in data or "tag" not in data:
                    images.append(
                        {
                            "path": ".".join(path_parts + [str(key)]),
                            "repository_obj": data,  # Reference to the dictionary holding the image string
                            "repository_key": str(
                                key
                            ),  # The key itself (e.g., 'image')
                            "tag_key": None,  # No separate tag key for this type
                            "current_repository": repository,
                            "current_tag": tag,
                            "type": "image_string",
                        }
                    )

            # Recurse for nested dictionaries and lists
            images.extend(find_images_in_values(value, path_parts + [str(key)]))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            images.extend(find_images_in_values(item, path_parts + [str(index)]))

    return images


# --- Registry API Interactions ---
def get_registry_type(repository: str) -> str:
    if repository.startswith("ghcr.io/"):
        return "ghcr.io"
    elif repository.startswith("quay.io/"):
        return "quay.io"
    elif repository.startswith("mcr.microsoft.com/"):
        return "mcr.microsoft.com"
    # Assumes docker.io if no explicit registry prefix or if it's a simple name like 'busybox'
    # and not an explicit domain like 'my.custom.registry/repo'
    elif not "/" in repository or (not "." in repository.split("/")[0]):
        return "docker.io"
    # Add more registries as needed
    return "unknown"


def get_docker_hub_tags(repository: str) -> list[tuple[str, datetime.datetime]]:
    repo_name = repository
    if "/" not in repo_name and not repo_name.startswith("library/"):
        repo_name = f"library/{repo_name}"

    url = f"https://hub.docker.com/v2/repositories/{repo_name}/tags/?page_size=100"
    tags_with_dates = []
    while url:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            for t in data["results"]:
                try:
                    # Docker Hub's last_updated is ISO 8601 string
                    timestamp = datetime.datetime.fromisoformat(
                        t["last_updated"].replace("Z", "+00:00")
                    )
                    tags_with_dates.append((t["name"], timestamp))
                except (ValueError, KeyError) as e:
                    print(
                        f"Warning: Could not parse timestamp for tag {t['name']} in {repository}: {e}",
                        file=sys.stderr,
                    )
            url = data["next"]
        except requests.exceptions.RequestException as e:
            print(
                f"Error fetching Docker Hub tags for {repository}: {e}", file=sys.stderr
            )
            return []
    return tags_with_dates


def get_ghcr_tags(repository: str) -> list[str]:
    parts = repository.split("/")
    if len(parts) < 3:
        print(f"Invalid ghcr.io repository format: {repository}", file=sys.stderr)
        return []

    repo_path = "/".join(parts[1:])

    token_url = f"https://ghcr.io/token?scope=repository:{repo_path}:pull"
    try:
        response = requests.get(token_url, timeout=10)
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            print(f"Error: GHCR token not found for {repository}", file=sys.stderr)
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error getting GHCR token for {repository}: {e}", file=sys.stderr)
        return []

    tags_url = f"https://ghcr.io/v2/{repo_path}/tags/list"
    try:
        response = requests.get(
            tags_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("tags", []) or []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching GHCR tags for {repository}: {e}", file=sys.stderr)
        return []


def get_quay_tags(repository: str) -> list[tuple[str, datetime.datetime]]:
    parts = repository.split("/")
    if len(parts) < 3:
        print(f"Invalid quay.io repository format: {repository}", file=sys.stderr)
        return []

    org = parts[1]
    repo_name = parts[2]

    url = f"https://quay.io/api/v1/repository/{org}/{repo_name}/tag/"
    tags_with_dates = []
    while url:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            for t in data["tags"]:
                try:
                    # Quay.io's last_modified is ISO 8601 string
                    timestamp = datetime.datetime.fromisoformat(
                        t["last_modified"].replace("Z", "+00:00")
                    )
                    tags_with_dates.append((t["name"], timestamp))
                except (ValueError, KeyError) as e:
                    print(
                        f"Warning: Could not parse timestamp for tag {t['name']} in {repository}: {e}",
                        file=sys.stderr,
                    )
            if "next_page" in data and data["next_page"]:
                url = f"https://quay.io{data['next_page']}"
            else:
                url = None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Quay.io tags for {repository}: {e}", file=sys.stderr)
            return []
    return tags_with_dates


def get_mcr_tags(repository: str) -> list[str]:
    parts = repository.split("/", 1)
    if len(parts) < 2:
        print(f"Invalid MCR repository format: {repository}", file=sys.stderr)
        return []

    registry = parts[0]
    repo_path = parts[1]

    # 1. Get token
    auth_url = f"https://{registry}/oauth2/token?service={registry}&scope=repository:{repo_path}:pull"
    try:
        response = requests.get(auth_url, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get("access_token")
        if not token:
            print(
                f"Error: MCR access token not found for {repository}", file=sys.stderr
            )
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error getting MCR token for {repository}: {e}", file=sys.stderr)
        return []

    tags_url = f"https://{registry}/v2/{repo_path}/tags/list"
    headers = {"Authorization": f"Bearer {token}"}
    all_tags = []
    current_tags_url = tags_url
    while current_tags_url:
        try:
            response = requests.get(current_tags_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            all_tags.extend(data.get("tags", []))

            current_tags_url = None
            if "Link" in response.headers:
                link_header = response.headers["Link"]
                match = re.search(r'<(.*)>; rel="next"', link_header)
                if match:
                    current_tags_url = match.group(1)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching MCR tags for {repository}: {e}", file=sys.stderr)
            return []
    return all_tags


# --- Tag Filtering and Selection ---
def get_latest_stable_tag(
    tags_with_dates: list[tuple[str, datetime.datetime]], min_age_days: int = 0
) -> str | None:
    stable_tags = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for tag, timestamp in tags_with_dates:
        # Filter out common non-stable indicators
        if re.search(
            r"\b(latest|snapshot|dev|nightly|test|alpha|beta|rc)\b", tag.lower()
        ):
            continue

        # Apply age filter if required and timestamp is available
        if min_age_days > 0 and timestamp != datetime.datetime.min:
            if (now - timestamp).days < min_age_days:
                # print(f"  Skipping {tag} (too new - published less than {min_age_days} days ago)")
                continue

        try:
            version = parse_version(tag)
            # Exclude pre-release and development versions
            if not version.is_prerelease and not version.is_devrelease:
                stable_tags.append(tag)
        except InvalidVersion:
            # If packaging.version can't parse it, it's not a version we care about for auto-upgrade
            continue

    if not stable_tags:
        return None

    # Sort versions and return the latest
    def version_sort_key(tag_name):
        clean_tag = tag_name.lstrip("v")
        try:
            return parse_version(clean_tag)
        except InvalidVersion:
            return parse_version("0.0.0")  # Fallback for malformed tags

    stable_tags.sort(key=version_sort_key, reverse=True)

    return stable_tags[0]


def get_tags_for_repository(registry_type: str, repository: str):
    if registry_type == "docker.io":
        return get_docker_hub_tags(repository)
    if registry_type == "ghcr.io":
        return get_ghcr_tags(repository)
    if registry_type == "quay.io":
        return get_quay_tags(repository)
    if registry_type == "mcr.microsoft.com":
        return get_mcr_tags(repository)
    return None


async def resolve_image_update(
    img_info, min_tag_age_days: int, image_semaphore: asyncio.Semaphore
):
    current_repository = img_info["current_repository"]
    current_tag = img_info["current_tag"]
    logs = []

    if not current_repository:
        logs.append(
            f"  Skipping malformed image entry at path {img_info['path']}: repository is empty."
        )
        return None, logs

    logs.append(
        f"  Checking image: {current_repository}:{current_tag} (Path: {img_info['path']})"
    )

    registry_type = get_registry_type(current_repository)
    if registry_type == "unknown":
        logs.append(
            f"  Warning: Unsupported registry type '{registry_type}' for {current_repository}. Skipping."
        )
        return None, logs

    async with image_semaphore:
        tags_raw = await asyncio.to_thread(
            get_tags_for_repository, registry_type, current_repository
        )

    tags_with_dates = []
    if tags_raw and isinstance(tags_raw[0], tuple):
        tags_with_dates = tags_raw
    elif tags_raw:
        logs.append(
            f"  Warning: Age filtering not available for {current_repository} (registry type: {registry_type}). All tags considered old enough."
        )
        tags_with_dates = [(tag, datetime.datetime.min) for tag in tags_raw]

    latest_stable_tag = get_latest_stable_tag(
        tags_with_dates, min_age_days=min_tag_age_days
    )

    if latest_stable_tag and latest_stable_tag != current_tag:
        logs.append(
            f"    Found new version: {latest_stable_tag} (current: {current_tag})"
        )
        return {"info": img_info, "new_tag": latest_stable_tag}, logs
    if latest_stable_tag:
        logs.append(f"    Already at latest stable version: {current_tag}")
        return None, logs

    logs.append(
        f"    No stable version found for {current_repository} with age >= {min_tag_age_days} days."
    )
    return None, logs


async def process_chart(
    chart_path: Path, min_tag_age_days: int, image_semaphore: asyncio.Semaphore
):
    logs = [f"Processing chart: {chart_path.name}"]

    if not chart_path.is_dir():
        logs.append(f"Error: Chart path '{chart_path}' is not a directory.")
        return 1, logs

    chart_yaml_path = chart_path / "Chart.yaml"
    values_yaml_path = chart_path / "values.yaml"

    if not chart_yaml_path.is_file():
        logs.append(f"Error: Chart.yaml not found in '{chart_path}'.")
        return 1, logs

    values_data = {}
    if values_yaml_path.is_file():
        values_data = load_yaml_file(values_yaml_path)
    else:
        logs.append(
            f"Warning: values.yaml not found in '{chart_path}'. Only Chart.yaml appVersion will be considered for upgrade if applicable."
        )

    chart_data = load_yaml_file(chart_yaml_path)
    images_in_values = find_images_in_values(values_data)

    image_tasks = [
        resolve_image_update(img_info, min_tag_age_days, image_semaphore)
        for img_info in images_in_values
    ]
    image_results = await asyncio.gather(*image_tasks)

    images_to_update = []
    for update_item, image_logs in image_results:
        logs.extend(image_logs)
        if update_item:
            images_to_update.append(update_item)

    # A chart is considered multi-container if it has more than one image definition found,
    # or if the single image definition is not the top-level 'image' object
    # (e.g., if it's nested like 'someApp.image').
    is_multi_container = len(images_in_values) > 1 or (
        len(images_in_values) == 1 and images_in_values[0]["path"] != "image"
    )

    # Determine update strategy
    if is_multi_container:
        logs.append(
            "  Chart identified as multi-container (or multiple images need update). Updating tags in values.yaml."
        )
        for update_item in images_to_update:
            img_info = update_item["info"]
            if img_info["type"] == "repo_tag_keys":
                existing_value = img_info["repository_obj"][img_info["tag_key"]]
                img_info["repository_obj"][img_info["tag_key"]] = apply_scalar_style(
                    update_item["new_tag"], existing_value
                )
                logs.append(
                    f"    Updated {img_info['path']}.{img_info['tag_key']} to {update_item['new_tag']}"
                )
            elif img_info["type"] == "image_string":
                new_full_image = (
                    f"{img_info['current_repository']}:{update_item['new_tag']}"
                )
                existing_value = img_info["repository_obj"][img_info["repository_key"]]
                img_info["repository_obj"][img_info["repository_key"]] = (
                    apply_scalar_style(new_full_image, existing_value)
                )
                logs.append(f"    Updated {img_info['path']} to {new_full_image}")

        if images_to_update:
            save_yaml_file(values_yaml_path, values_data)
            logs.append(f"  Updated values.yaml for {chart_path.name}")

    elif (
        images_to_update
    ):  # Single image found in values.yaml, and it's the main 'image' object or string
        update_item = images_to_update[0]
        img_info = update_item["info"]

        logs.append(
            "  Chart identified as single-container. Updating appVersion in Chart.yaml and tag in values.yaml."
        )
        # Update values.yaml
        if img_info["type"] == "repo_tag_keys":
            existing_value = img_info["repository_obj"][img_info["tag_key"]]
            img_info["repository_obj"][img_info["tag_key"]] = apply_scalar_style(
                update_item["new_tag"], existing_value
            )
            logs.append(
                f"    Updated {img_info['path']}.{img_info['tag_key']} to {update_item['new_tag']} in values.yaml"
            )
        elif img_info["type"] == "image_string":
            new_full_image = (
                f"{img_info['current_repository']}:{update_item['new_tag']}"
            )
            existing_value = img_info["repository_obj"][img_info["repository_key"]]
            img_info["repository_obj"][img_info["repository_key"]] = apply_scalar_style(
                new_full_image, existing_value
            )
            logs.append(
                f"    Updated {img_info['path']} to {new_full_image} in values.yaml"
            )

        save_yaml_file(values_yaml_path, values_data)

        # Update Chart.yaml appVersion
        chart_data["appVersion"] = apply_scalar_style(
            update_item["new_tag"], chart_data.get("appVersion")
        )
        save_yaml_file(chart_yaml_path, chart_data)
        logs.append(f"    Updated appVersion in Chart.yaml to {update_item['new_tag']}")
    else:
        logs.append("  No upgradeable images found or no changes needed.")

    logs.append(f"Finished processing chart: {chart_path.name}")
    return 0, logs


async def process_chart_with_semaphore(
    chart_path: Path,
    min_tag_age_days: int,
    chart_semaphore: asyncio.Semaphore,
    image_semaphore: asyncio.Semaphore,
):
    async with chart_semaphore:
        return chart_path, await process_chart(
            chart_path, min_tag_age_days, image_semaphore
        )


async def async_main(args) -> int:
    if args.min_tag_age_days < 0:
        print("Error: --min-tag-age-days cannot be negative.", file=sys.stderr)
        return 1
    if args.chart_concurrency < 1:
        print("Error: --chart-concurrency must be at least 1.", file=sys.stderr)
        return 1
    if args.image_concurrency < 1:
        print("Error: --image-concurrency must be at least 1.", file=sys.stderr)
        return 1

    chart_semaphore = asyncio.Semaphore(args.chart_concurrency)
    image_semaphore = asyncio.Semaphore(args.image_concurrency)
    tasks = [
        process_chart_with_semaphore(
            chart_path,
            args.min_tag_age_days,
            chart_semaphore,
            image_semaphore,
        )
        for chart_path in args.chart_paths
    ]

    overall_exit_code = 0
    for chart_path, (exit_code, logs) in await asyncio.gather(*tasks):
        del chart_path
        for line in logs:
            print(line)
        if exit_code != 0:
            overall_exit_code = exit_code

    return overall_exit_code


def main():
    args = parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
