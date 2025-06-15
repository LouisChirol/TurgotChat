#!/bin/bash

# Server details
SERVER="ubuntu@145.239.71.174"
DEST_DIR="~/colbert"

# Create a temporary directory for the clean copy
TEMP_DIR=$(mktemp -d)

# Copy frontend (excluding node_modules and .next)
rsync -av --exclude 'node_modules' \
        --exclude '.next' \
        --exclude '.git' \
        frontend/ $TEMP_DIR/frontend/

# Verify public directory was copied
if [ ! -d "$TEMP_DIR/frontend/public" ]; then
    echo "Error: public directory not found in frontend!"
    exit 1
else
    echo "Public directory found in frontend!"
fi

# Copy backend (excluding __pycache__ and .venv)
rsync -av --exclude '__pycache__' \
        --exclude '.venv' \
        --exclude '.git' \
        backend/ $TEMP_DIR/backend/

# Create database directory in temp location
mkdir -p $TEMP_DIR/database

# Copy database (only chroma_db subfolder)
rsync -av --exclude '.git' database/chroma_db/ $TEMP_DIR/database/chroma_db/

# Copy other necessary files
cp docker-compose.yml $TEMP_DIR/
cp scripts/setup-server.sh $TEMP_DIR/

# Copy everything to the server
scp  -i ~/.ssh/id_ed25519_colbert -r $TEMP_DIR/* $SERVER:$DEST_DIR/

# Verify public directory on server
ssh -i ~/.ssh/id_ed25519_colbert $SERVER "ls -la $DEST_DIR/frontend/public/"

# Clean up
rm -rf $TEMP_DIR

echo "Files copied successfully! Now SSH into the server and run:"
echo "cd ~/colbert && ./setup-server.sh" 