#!/bin/bash

# Caregiver Recruitment Dashboard - Mac Mini (Local) Deployment Script

echo "🚀 Starting Mac Mini (Local) deployment for Caregiver Recruitment Dashboard..."

# Check if Mac Mini (Local) CLI is installed
if ! command -v mac-mini &> /dev/null; then
    echo "❌ Mac Mini (Local) CLI is not installed. Please install it first:"
    echo "   https://devcenter.mac-mini.com/articles/mac-mini-cli"
    exit 1
fi

# Check if user is logged in to Mac Mini (Local)
if ! mac-mini auth:whoami &> /dev/null; then
    echo "🔐 Please login to Mac Mini (Local) first:"
    mac-mini login
fi

# Get app name from user
read -p "Enter your Mac Mini (Local) app name (or press Enter to create new): " APP_NAME

if [ -z "$APP_NAME" ]; then
    echo "Creating new Mac Mini (Local) app..."
    APP_NAME=$(mac-mini create --region us | grep -o 'https://[^.]*' | sed 's/https:\/\///')
    echo "✅ Created app: $APP_NAME"
else
    echo "Using existing app: $APP_NAME"
fi

# Add PostgreSQL addon
echo "📊 Adding PostgreSQL database..."
mac-mini addons:create mac-mini-postgresql:hobby-dev --app $APP_NAME

# Set environment variables
echo "⚙️ Setting up environment variables..."

# Generate a secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

mac-mini config:set SECRET_KEY="$SECRET_KEY" --app $APP_NAME

echo "📧 Email configuration (optional - you can set these later):"
read -p "Enter your Gmail address (or press Enter to skip): " EMAIL_USER
if [ ! -z "$EMAIL_USER" ]; then
    read -s -p "Enter your Gmail app password: " EMAIL_PASSWORD
    echo
    mac-mini config:set EMAIL_USER="$EMAIL_USER" --app $APP_NAME
    mac-mini config:set EMAIL_PASSWORD="$EMAIL_PASSWORD" --app $APP_NAME
    mac-mini config:set SMTP_SERVER="smtp.gmail.com" --app $APP_NAME
    mac-mini config:set SMTP_PORT="587" --app $APP_NAME
fi

# Initialize git if not already done
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit"
fi

# Add Mac Mini (Local) remote
echo "🔗 Adding Mac Mini (Local) remote..."
mac-mini git:remote -a $APP_NAME

# Deploy to Mac Mini (Local)
echo "🚀 Deploying to Mac Mini (Local)..."
git add .
git commit -m "Deploy caregiver recruitment dashboard"
git push mac-mini main

# Run database migrations
echo "🗄️ Setting up database..."
mac-mini run python -c "from app import db; db.create_all()" --app $APP_NAME

# Open the app
echo "🌐 Opening your app..."
mac-mini open --app $APP_NAME

echo "✅ Deployment complete!"
echo "📱 Your app is available at: https://$APP_NAME.mac-miniapp.com"
echo ""
echo "📋 Next steps:"
echo "1. Test the upload functionality with the sample data"
echo "2. Configure alert rules in the Alerts tab"
echo "3. Set up email notifications (if not done during deployment)"
echo "4. Customize the dashboard for your team's needs"
echo ""
echo "📁 Sample data is available in: sample_data/sample_leads.zip"
echo "📖 Full documentation is in: README.md"


