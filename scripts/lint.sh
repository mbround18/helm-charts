#!/bin/bash

cd "$(dirname "$0")" || exit 1
cd ..

npx -y prettier --write . 

# Find all directories containing Chart.yaml
for dir in $(find . -type f -name 'Chart.yaml' -printf '%h\n'); do
  # Navigate to the directory
  cd $dir
  # Run helm lint
  helm lint .
  # Navigate back to the original directory
  cd -
done

