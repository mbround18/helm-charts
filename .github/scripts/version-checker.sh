#!/bin/bash

log() {
  local level="$1"
  shift
  local message="$*"
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $message"
}

# Fetch all tags from the remote repository
git fetch --tags

# Check if the script is running in a merge request context (dry run mode)
DRY_RUN=false
if [ "$GITHUB_EVENT_NAME" == "pull_request" ]; then
  DRY_RUN=true
  log "INFO" "Running in dry run mode for a merge request."
  SUMMARY_FILE="$GITHUB_STEP_SUMMARY"
fi

# Loop through all charts in the charts directory
for chart in charts/*; do
  if [ ! -d "$chart" ]; then
    log "WARNING" "$chart is not a directory, skipping."
    continue
  fi

  chart_name="$(basename "$chart")"
  CHART_PATH="$chart/Chart.yaml"
  log "INFO" "Processing chart: $chart_name"
  log "INFO" "Chart path: $CHART_PATH"

  if [ ! -f "$CHART_PATH" ]; then
    log "WARNING" "Chart.yaml not found for $chart_name, skipping."
    continue
  fi

  CHART_TAG="$(git tag -l "$chart_name-*" | sort -V | tail -n 1)"

  if [ -z "$CHART_TAG" ]; then
    log "WARNING" "No previous tag found for $chart_name, skipping version bump."
    if [ "$DRY_RUN" == true ]; then
      echo "- Chart: $chart_name - No previous tag found, skipping version bump." >> "$SUMMARY_FILE"
    fi
    continue
  fi

  CHART_VERSION="${CHART_TAG#*-}"
  log "INFO" "Latest tag found: $CHART_TAG (version: $CHART_VERSION)"
  LAST_TAG_COMMIT="$(git rev-list -n 1 "$CHART_TAG")"
  log "INFO" "Last tag commit: $LAST_TAG_COMMIT"

  # Check if there have been changes since the last tag commit
  # Detect any changes within the chart directory since the last release
  CHANGED="$(git diff --name-only "$LAST_TAG_COMMIT"..HEAD -- "$chart")"
  if [ -z "$CHANGED" ]; then
    log "INFO" "No changes found for $chart_name since last release, skipping version bump."
    if [ "$DRY_RUN" == true ]; then
      echo "- Chart: $chart_name - No changes since last release, skipping version bump." >> "$SUMMARY_FILE"
    fi
    continue
  fi

  log "INFO" "Changes detected for $chart_name since the last release. Determining version bump type..."

  # Determine bump type based on commit messages
  bump_type="patch"
  while read -r commit_hash; do
    log "INFO" "Evaluating commit: $commit_hash"
    commit_message="$(git log --format=%B -n 1 "$commit_hash")"
    log "INFO" "Commit message: $commit_message"
    pr_number="$(echo "$commit_message" | grep -oE '#[0-9]+' | tr -d '#')"
    if [ -n "$pr_number" ]; then
      log "INFO" "Detected PR reference: #$pr_number"
      if command -v gh >/dev/null 2>&1; then
        pr_labels="$(gh pr view "$pr_number" --json labels --jq '.labels[].name' 2>/dev/null || true)"
        log "INFO" "PR labels: $pr_labels"
      else
        pr_labels=""
        log "WARNING" "GitHub CLI (gh) not available; defaulting to patch bump when labels are needed."
      fi
      if echo "$pr_labels" | grep -q "major"; then
        bump_type="major"
        log "INFO" "Major version label detected, setting bump type to major."
        break
      elif echo "$pr_labels" | grep -q "minor"; then
        bump_type="minor"
        log "INFO" "Minor version label detected, setting bump type to minor."
      else
        log "INFO" "No relevant labels found, defaulting to patch."
      fi
    else
      log "INFO" "No PR reference found in commit message, defaulting to patch."
    fi
  done < <(git log --format="%H" "$LAST_TAG_COMMIT"..HEAD -- "$chart")

  log "INFO" "Determined bump type: $bump_type"

  # Bump the version accordingly
  IFS='.' read -r -a parts <<< "$CHART_VERSION"
  case $bump_type in
    patch)
      ((parts[2]++))
      log "INFO" "Bumping patch version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
    minor)
      ((parts[1]++))
      parts[2]=0
      log "INFO" "Bumping minor version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
    major)
      ((parts[0]++))
      parts[1]=0
      parts[2]=0
      log "INFO" "Bumping major version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
  esac
  new_version="${parts[0]}.${parts[1]}.${parts[2]}"

  # Read the current version in Chart.yaml
  CURRENT_VERSION="$(yq eval '.version' "$CHART_PATH")"
  log "INFO" "Current Chart.yaml version: $CURRENT_VERSION"

  if [ "$DRY_RUN" == true ]; then
    echo "- Chart: $chart_name - Bump type: $bump_type - New version: $new_version" >> "$SUMMARY_FILE"
  else
    if [ "$CURRENT_VERSION" == "$new_version" ]; then
      log "INFO" "$chart_name already at target version ($new_version), skipping update."
    else
      # Update the chart version
      log "INFO" "Updating chart version in $CHART_PATH to $new_version"
      yq eval -i ".version = \"$new_version\"" "$CHART_PATH"

      # Only commit if file actually changed
      if git diff --quiet -- "$CHART_PATH"; then
        log "INFO" "No changes detected in $CHART_PATH after update, skipping commit."
      else
        log "INFO" "Staging changes for $chart_name"
        git add "$CHART_PATH"
        git commit -m "[skip ci] Robot commit: Bumping chart version for $chart_name to $new_version" || {
          log "WARNING" "Git commit failed (possibly no changes); continuing."
        }
        log "INFO" "Version bump commit created for $chart_name"
      fi
    fi
  fi
done

if [ "$DRY_RUN" == false ]; then
  # Push changes to the remote repository
  log "INFO" "Pushing changes to remote..."
  # Normalize ref (e.g., refs/heads/main) to branch name
  BRANCH_NAME="${GITHUB_REF#refs/heads/}"
  git push origin "HEAD:${BRANCH_NAME}"
fi
