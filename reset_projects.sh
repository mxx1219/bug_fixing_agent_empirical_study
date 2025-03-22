#!/bin/bash

# Set the path to the projects directory
PROJECTS_DIR="./swe_projects/"

# Enter the projects directory
cd "$PROJECTS_DIR" || exit

# Iterate over each subfolder
for project in */; do
  # Enter the subfolder
  cd "$project" || continue
  
  # Run git commands
  git reset --hard HEAD  # Discard local changes
  git clean -fd          # Remove untracked files and directories
  
  # Return to the projects directory
  cd ..
done

echo "Operation completed"