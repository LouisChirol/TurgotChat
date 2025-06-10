#!/bin/bash

# Update system
sudo apt update
sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose

# Add current user to docker group
sudo usermod -aG docker $USER

# Install Nginx
sudo apt install -y nginx

# Configure Nginx
sudo tee /etc/nginx/sites-available/colbertchat << EOF
server {
    listen 80;
    server_name colbertchat.fr www.colbertchat.fr;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}

server {
    listen 80;
    server_name api.colbertchat.fr;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/colbertchat /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Install Certbot for SSL
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificates
sudo certbot --nginx -d colbertchat.fr -d www.colbertchat.fr -d api.colbertchat.fr

# Set environment variables
export MISTRAL_API_KEY=your-api-key
export TAVILY_API_KEY=your-api-key

# Build and start containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "Setup complete! Your application is running at https://colbertchat.fr" 