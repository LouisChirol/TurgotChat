#!/bin/bash

# Create directory if it doesn't exist
mkdir -p ~/colbert
cd ~/colbert

# Ensure logs directory exists with proper permissions
mkdir -p backend/logs
chmod 777 backend/logs

# Copy Nginx configuration
echo "Updating Nginx configuration..."
sudo cp nginx/colbertchat.fr.conf /etc/nginx/sites-available/colbertchat.fr
sudo ln -sf /etc/nginx/sites-available/colbertchat.fr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Copy production environment file
echo "Setting up environment files..."
cp frontend/.env.production frontend/.env

# Stop and remove existing containers
docker-compose down

# Build and start containers
docker-compose up -d --build

# Show container status
docker-compose ps

echo "Deployment complete! Your application is running at https://colbertchat.fr"
echo "Logs are available at ~/colbert/backend/logs/colbert_backend.log" 