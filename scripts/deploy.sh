#!/bin/bash

# Create directory if it doesn't exist
mkdir -p ~/turgot
cd ~/turgot

# Ensure logs directory exists with proper permissions
mkdir -p backend/logs
chmod 777 backend/logs

# Copy Nginx configuration
echo "Updating Nginx configuration..."
sudo cp nginx/turgotchat.fr.conf /etc/nginx/sites-available/turgotchat.fr
sudo ln -sf /etc/nginx/sites-available/turgotchat.fr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Copy production environment file
echo "Setting up environment files..."
cp frontend/.env.production frontend/.env

# Stop and remove existing containers
docker-compose down

# Build and start containers
docker compose up -d --build frontend backend redis

# Show container status 
docker-compose ps

echo "Deployment complete! Your application is running at https://turgotchat.fr"
echo "Logs are available at ~/turgot/backend/logs/turgot_backend.log" 