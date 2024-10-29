#!/bin/bash

CHARTS=$@

# Fetch all tags from the remote repository
git fetch --tags

for chart in $CHARTS; do
  echo "Processing chart: $chart"
  CHART_PATH="charts/$chart/Chart.yaml"
  echo "Chart path: $CHART_PATH"
  CHART_TAG=$(git tag -l "$chart-*" | sort -V | tail -n 1)

  if [ -z "$CHART_TAG" ]; then
    echo "No previous tag found for $chart, skipping version bump."
    continue
  fi

  CHART_VERSION=${CHART_TAG#*-}
  echo "Latest tag found: $CHART_TAG (version: $CHART_VERSION)"
  LAST_TAG_COMMIT=$(git rev-list -n 1 "$CHART_TAG")
  echo "Last tag commit: $LAST_TAG_COMMIT"

  # Check if there have been changes since the last tag commit
  CHANGED=$(git diff --name-only $LAST_TAG_COMMIT..HEAD -- $CHART_PATH)
  if [ -z "$CHANGED" ]; then
    echo "No changes found for $chart since last release, skipping version bump."
    continue
  fi

  echo "Changes detected for $chart since the last release. Determining version bump type..."

  # Determine bump type based on commit messages
  bump_type="patch"
  while read -r commit_hash; do
    echo "Evaluating commit: $commit_hash"
    commit_message=$(git log --format=%B -n 1 $commit_hash)
    echo "Commit message: $commit_message"
    pr_number=$(echo "$commit_message" | grep -oE '#[0-9]+' | tr -d '#')
    if [ -n "$pr_number" ]; then
      echo "Detected PR reference: #$pr_number"
      pr_labels=$(gh pr view $pr_number --json labels --jq '.labels[].name')
      echo "PR labels: $pr_labels"
      if echo "$pr_labels" | grep -q "major"; then
        bump_type="major"
        echo "Major version label detected, setting bump type to major."
        break
      elif echo "$pr_labels" | grep -q "minor"; then
        bump_type="minor"
        echo "Minor version label detected, setting bump type to minor."
      else
        echo "No relevant labels found, defaulting to patch."
      fi
    else
      echo "No PR reference found in commit message, defaulting to patch."
    fi
  done < <(git log --format="%H" $LAST_TAG_COMMIT..HEAD -- $CHART_PATH)

  echo "Determined bump type: $bump_type"

  # Bump the version accordingly
  IFS='.' read -r -a parts <<< "$CHART_VERSION"
  case $bump_type in
    patch)
      ((parts[2]++))
      echo "Bumping patch version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
    minor)
      ((parts[1]++))
      parts[2]=0
      echo "Bumping minor version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
    major)
      ((parts[0]++))
      parts[1]=0
      parts[2]=0
      echo "Bumping major version: ${parts[0]}.${parts[1]}.${parts[2]}"
      ;;
  esac
  new_version="${parts[0]}.${parts[1]}.${parts[2]}"

  # Update the chart version
  echo "Updating chart version in $CHART_PATH to $new_version"
  yq eval -i ".version = \"$new_version\"" $CHART_PATH

  echo "Staging changes for $chart"
  git add $CHART_PATH
  git commit -m "[skip ci] Robot commit: Bumping chart version for $chart to $new_version"
  echo "Version bump commit created for $chart"
done

# Push changes to the remote repository
echo "Pushing changes to remote..."
git push origin $GITHUB_REF
