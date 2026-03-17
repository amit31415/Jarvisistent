#!/bin/bash

# Define the working directory
PROJECT_DIR="/home/kido1/Smartroom/core_production"

echo "[INFO] Starting auto-backup for Jarvis OS..."
cd $PROJECT_DIR

# Check if there are any changes in the directory
if [ -n "$(git status --porcelain)" ]; then
    echo "[INFO] Changes detected. Adding to Git..."
    git add .
    
    # Create a commit with the current date and time
    COMMIT_MSG="Auto-backup: $(date +'%Y-%m-%d %H:%M:%S')"
    git commit -m "$COMMIT_MSG"
    
    echo "[INFO] Pushing to remote repository..."
    git push origin main
    
    echo "[SUCCESS] Backup completed: $COMMIT_MSG"
else
    echo "[INFO] No changes to backup. Directory is clean."
fi