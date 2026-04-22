import argparse
import os
import re
import requests
import subprocess
import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from packaging.version import parse as parse_version, InvalidVersion

def load_yaml_file(filepath: Path):
    yaml = YAML()
    with open(filepath, 'r') as f:
        return yaml.load(f)

def save_yaml_file(filepath: Path, data):
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(filepath, 'w') as f:
        yaml.dump(data, f)

def find_images_in_values(data, path_parts=None):
    if path_parts is None:
        path_parts = []

    images = []

    if isinstance(data, dict) or isinstance(data, CommentedMap):
        # Type 1: Dictionary with separate 'repository' and 'tag' keys
        if "repository" in data and "tag" in data:
            images.append({
                "path": ".".join(path_parts),
                "repository_obj": data, # Reference to the dictionary holding 'repository' and 'tag'
                "repository_key": "repository",
                "tag_key": "tag",
                "current_repository": data["repository"],
                "current_tag": data["tag"],
                "type": "repo_tag_keys"
            })
        
        # Type 2: Key named 'image' (or similar) with a string value like "repo/image:tag"
        for key, value in data.items():
            if isinstance(value, str) and (key == "image" or key.endswith("Image")): # Heuristic for image strings
                full_image_str = value
                repository = full_image_str
                tag = ""
                
                # Attempt to parse into repository and tag
                if ":" in full_image_str:
                    repository, tag = full_image_str.rsplit(":", 1)
                
                # Avoid adding duplicates if already caught by Type 1 (e.g. `image: {repository: foo, tag: bar}`)
                # This might happen if 'image' is a sub-key of a larger image object
                if "repository" not in data or "tag" not in data:
                    images.append({
                        "path": ".".join(path_parts + [str(key)]),
                        "repository_obj": data, # Reference to the dictionary holding the image string
                        "repository_key": str(key), # The key itself (e.g., 'image')
                        "tag_key": None, # No separate tag key for this type
                        "current_repository": repository,
                        "current_tag": tag,
                        "type": "image_string"
                    })
            
            # Recurse for nested dictionaries and lists
            images.extend(find_images_in_values(value, path_parts + [str(key)]))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            images.extend(find_images_in_values(item, path_parts + [str(index)]))
    
    return images

def get_registry_type(repository: str) -> str:
    if repository.startswith("ghcr.io/"):
        return "ghcr.io"
    elif repository.startswith("quay.io/"): # Added quay.io
        return "quay.io"
    elif "/" in repository and "." not in repository.split("/")[0] and not repository.startswith("mcr.microsoft.com/"): # Simple check for docker.io
        return "docker.io"
    elif repository.startswith("mcr.microsoft.com/"): # Microsoft Container Registry
        return "mcr.microsoft.com"
    # Add more registries as needed
    return "unknown"

def get_docker_hub_tags(repository: str) -> list[str]:
    # For Docker Hub, the repository name might be 'library/ubuntu' for official images
    # or 'user/repo' for others. The API expects 'library/ubuntu' or 'user/repo'.
    repo_name = repository
    if '/' not in repo_name and not repo_name.startswith("library/"):
        repo_name = f"library/{repo_name}" # Assume official image if no '/'

    url = f"https://hub.docker.com/v2/repositories/{repo_name}/tags/?page_size=100"
    tags = []
    while url:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            tags.extend([t['name'] for t in data['results']])
            url = data['next']
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Docker Hub tags for {repository}: {e}", file=sys.stderr)
            return []
    return tags

def get_ghcr_tags(repository: str) -> list[str]:
    # Check for jq
    if subprocess.run(["which", "jq"], capture_output=True).returncode != 0:
        print("Error: 'jq' is required to fetch tags from ghcr.io but is not installed.", file=sys.stderr)
        print("Please install 'jq' (e.g., sudo apt-get install jq or brew install jq).", file=sys.stderr)
        return []

    # GHCR repository format: ghcr.io/owner/repo
    parts = repository.split('/')
    if len(parts) < 2: # ghcr.io/owner/repo or ghcr.io/repo for org-level
        print(f"Invalid ghcr.io repository format: {repository}", file=sys.stderr)
        return []
    
    # owner_repo = "/".join(parts[1:]) # e.g., actions/actions-runner, or just 'repo' for org-level
    # The GHCR API path structure is /v2/OWNER/REPO/tags/list, so we need the full path after ghcr.io
    repo_path = "/".join(parts[1:])

    # 1. Get token
    token_url = f"https://ghcr.io/token?scope=repository:{repo_path}:pull"
    try:
        token_proc = subprocess.run(["curl", "-s", "--connect-timeout", "10", token_url], capture_output=True, text=True, check=True)
        token_json = token_proc.stdout
        token = subprocess.run(["jq", "-r", ".token"], input=token_json, capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, Exception) as e:
        print(f"Error getting GHCR token for {repository}: {e}", file=sys.stderr)
        return []

    # 2. List tags
    tags_url = f"https://ghcr.io/v2/{repo_path}/tags/list"
    try:
        tags_proc = subprocess.run(["curl", "-s", "-H", f"Authorization: Bearer {token}", "--connect-timeout", "10", tags_url], capture_output=True, text=True, check=True)
        tags_json = tags_proc.stdout
        tags_data = subprocess.run(["jq", "-r", ".tags[]"], input=tags_json, capture_output=True, text=True, check=True).stdout.splitlines()
        return tags_data
    except (subprocess.CalledProcessError, Exception) as e:
        print(f"Error fetching GHCR tags for {repository}: {e}", file=sys.stderr)
        return []

def get_quay_tags(repository: str) -> list[str]:
    # quay.io/organization/repository
    parts = repository.split('/')
    if len(parts) < 3:
        print(f"Invalid quay.io repository format: {repository}", file=sys.stderr)
        return []
    
    org = parts[1]
    repo_name = parts[2]

    url = f"https://quay.io/api/v1/repository/{org}/{repo_name}/tag/"
    tags = []
    while url:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            tags.extend([t['name'] for t in data['tags']])
            if 'next_page' in data and data['next_page']:
                url = f"https://quay.io{data['next_page']}"
            else:
                url = None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Quay.io tags for {repository}: {e}", file=sys.stderr)
            return []
    return tags

def get_mcr_tags(repository: str) -> list[str]:
    # MCR requires fetching a token first
    # Example: mcr.microsoft.com/azure-cli
    
    # Split repository into registry and repo_path
    parts = repository.split('/', 1)
    if len(parts) < 2:
        print(f"Invalid MCR repository format: {repository}", file=sys.stderr)
        return []
    
    registry = parts[0] # Should be mcr.microsoft.com
    repo_path = parts[1] # e.g., azure-cli

    # 1. Get token
    auth_url = f"https://{registry}/oauth2/token?service={registry}&scope=repository:{repo_path}:pull"
    try:
        response = requests.get(auth_url, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get('access_token')
        if not token:
            print(f"Error: MCR access token not found for {repository}", file=sys.stderr)
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error getting MCR token for {repository}: {e}", file=sys.stderr)
        return []

    # 2. List tags
    tags_url = f"https://{registry}/v2/{repo_path}/tags/list"
    headers = {"Authorization": f"Bearer {token}"}
    tags = []
    while tags_url:
        try:
            response = requests.get(tags_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            tags.extend(data.get('tags', []))
            
            # Check for pagination link
            tags_url = None
            if 'Link' in response.headers:
                # Example: Link: <https://mcr.microsoft.com/v2/azure-cli/tags/list?n=100&last=2.0.1>; rel="next"
                link_header = response.headers['Link']
                match = re.search(r'<(.*)>; rel="next"', link_header)
                if match:
                    tags_url = match.group(1)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching MCR tags for {repository}: {e}", file=sys.stderr)
            return []
    return tags


def get_latest_stable_tag(tags: list[str]) -> str | None:
    stable_tags = []
    for tag in tags:
        # Filter out common non-stable indicators
        if any(keyword in tag.lower() for keyword in ["latest", "snapshot", "dev", "nightly", "test", "rc", "beta", "alpha"]):
            continue
        # Further refine filtering for tags that are not clearly version numbers
        # This regex allows semver-like strings, possibly with 'v' prefix, but not arbitrary strings
        if re.match(r"^(v)?\d+(\.\d+){0,2}(\.\d+)?(-.+)?$", tag) is None:
            continue
        
        try:
            version = parse_version(tag)
            # Exclude pre-release versions even if parse_version might consider them valid
            if not version.is_prerelease and not version.is_devrelease:
                stable_tags.append(tag)
        except InvalidVersion:
            # If packaging.version can't parse it, it's not a version we care about
            continue
    
    if not stable_tags:
        return None

    # Sort versions and return the latest
    # Custom sort key to handle 'v' prefix and ensure correct semantic versioning
    def version_sort_key(tag):
        # Remove 'v' prefix for parsing by packaging.version
        clean_tag = tag.lstrip('v')
        try:
            return parse_version(clean_tag)
        except InvalidVersion:
            # For tags that still can't be parsed after cleaning, assign a very low version
            return parse_version("0.0.0")

    stable_tags.sort(key=version_sort_key, reverse=True)
    
    return stable_tags[0]


def main():
    parser = argparse.ArgumentParser(description="Upgrade container image tags in Helm charts.")
    parser.add_argument("chart_path", type=Path, help="Path to the Helm chart directory (e.g., charts/my-chart)")
    args = parser.parse_args()

    chart_path: Path = args.chart_path

    if not chart_path.is_dir():
        print(f"Error: Chart path '{chart_path}' is not a directory.")
        exit(1)

    chart_yaml_path = chart_path / "Chart.yaml"
    values_yaml_path = chart_path / "values.yaml"

    if not chart_yaml_path.is_file():
        print(f"Error: Chart.yaml not found in '{chart_path}'.")
        exit(1)

    values_data = {}
    if values_yaml_path.is_file():
        values_data = load_yaml_file(values_yaml_path)
    else:
        print(f"Warning: values.yaml not found in '{chart_path}'. Only Chart.yaml appVersion will be considered for upgrade if applicable.")


    print(f"Processing chart: {chart_path.name}")

    chart_data = load_yaml_file(chart_yaml_path)
    
    # Identify images in values.yaml
    images_in_values = find_images_in_values(values_data)
    
    # Process images for upgrade
    images_to_update = []
    for img_info in images_in_values:
        current_repository = img_info["current_repository"]
        current_tag = img_info["current_tag"]

        if not current_repository:
            print(f"  Skipping malformed image entry at path {img_info['path']}: repository is empty.")
            continue
        
        print(f"  Checking image: {current_repository}:{current_tag} (Path: {img_info['path']})")
        
        registry_type = get_registry_type(current_repository)
        tags = []
        if registry_type == "docker.io":
            tags = get_docker_hub_tags(current_repository)
        elif registry_type == "ghcr.io":
            tags = get_ghcr_tags(current_repository)
        elif registry_type == "quay.io":
            tags = get_quay_tags(current_repository)
        elif registry_type == "mcr.microsoft.com":
            tags = get_mcr_tags(current_repository)
        else:
            print(f"  Warning: Unsupported registry type '{registry_type}' for {current_repository}. Skipping.", file=sys.stderr)
            continue
        
        latest_stable_tag = get_latest_stable_tag(tags)
        
        if latest_stable_tag and latest_stable_tag != current_tag:
            print(f"    Found new version: {latest_stable_tag} (current: {current_tag})")
            images_to_update.append({
                "info": img_info,
                "new_tag": latest_stable_tag
            })
        elif latest_stable_tag:
            print(f"    Already at latest stable version: {current_tag}")
        else:
            print(f"    No stable version found for {current_repository}", file=sys.stderr)

    # A chart is considered multi-container if it has more than one image definition found,
    # or if the single image definition is not the top-level 'image' object
    # (e.g., if it's nested like 'someApp.image').
    is_multi_container = len(images_in_values) > 1 or \
                         (len(images_in_values) == 1 and images_in_values[0]["path"] != "image")
    
    # Determine update strategy
    if is_multi_container:
        print("  Chart identified as multi-container (or multiple images need update). Updating tags in values.yaml.")
        for update_item in images_to_update:
            img_info = update_item["info"]
            if img_info["type"] == "repo_tag_keys":
                img_info["repository_obj"][img_info["tag_key"]] = update_item["new_tag"]
                print(f"    Updated {img_info['path']}.{img_info['tag_key']} to {update_item['new_tag']}")
            elif img_info["type"] == "image_string":
                # Reconstruct the full image string
                new_full_image = f"{img_info['current_repository']}:{update_item['new_tag']}"
                img_info["repository_obj"][img_info["repository_key"]] = new_full_image
                print(f"    Updated {img_info['path']} to {new_full_image}")

        if images_to_update:
            save_yaml_file(values_yaml_path, values_data)
            print(f"  Updated values.yaml for {chart_path.name}")

    elif images_to_update: # Single image found in values.yaml, and it's the main 'image' object or string
        update_item = images_to_update[0]
        img_info = update_item["info"]
        
        print("  Chart identified as single-container. Updating appVersion in Chart.yaml and tag in values.yaml.")
        # Update values.yaml
        if img_info["type"] == "repo_tag_keys":
            img_info["repository_obj"][img_info["tag_key"]] = update_item["new_tag"]
            print(f"    Updated {img_info['path']}.{img_info['tag_key']} to {update_item['new_tag']} in values.yaml")
        elif img_info["type"] == "image_string":
            new_full_image = f"{img_info['current_repository']}:{update_item['new_tag']}"
            img_info["repository_obj"][img_info["repository_key"]] = new_full_image
            print(f"    Updated {img_info['path']} to {new_full_image} in values.yaml")

        save_yaml_file(values_yaml_path, values_data)

        # Update Chart.yaml appVersion
        chart_data["appVersion"] = update_item["new_tag"]
        save_yaml_file(chart_yaml_path, chart_data)
        print(f"    Updated appVersion in Chart.yaml to {update_item['new_tag']}")
    else:
        print("  No upgradeable images found or no changes needed.")

    print(f"Finished processing chart: {chart_path.name}")
    
if __name__ == "__main__":
    main()
