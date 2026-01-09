#!/bin/bash

# Caregiver Recruitment Dashboard - Heroku Deployment Script

echo "🚀 Starting Heroku deployment for Caregiver Recruitment Dashboard..."

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI is not installed. Please install it first:"
    echo "   https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Check if user is logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "🔐 Please login to Heroku first:"
    heroku login
fi

# Get app name from user
read -p "Enter your Heroku app name (or press Enter to create new): " APP_NAME

if [ -z "$APP_NAME" ]; then
    echo "Creating new Heroku app..."
    APP_NAME=$(heroku create --region us | grep -o 'https://[^.]*' | sed 's/https:\/\///')
    echo "✅ Created app: $APP_NAME"
else
    echo "Using existing app: $APP_NAME"
fi

# Add PostgreSQL addon
echo "📊 Adding PostgreSQL database..."
heroku addons:create heroku-postgresql:hobby-dev --app $APP_NAME

# Set environment variables
echo "⚙️ Setting up environment variables..."

# Generate a secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

heroku config:set SECRET_KEY="$SECRET_KEY" --app $APP_NAME

echo "📧 Email configuration (optional - you can set these later):"
read -p "Enter your Gmail address (or press Enter to skip): " EMAIL_USER
if [ ! -z "$EMAIL_USER" ]; then
    read -s -p "Enter your Gmail app password: " EMAIL_PASSWORD
    echo
    heroku config:set EMAIL_USER="$EMAIL_USER" --app $APP_NAME
    heroku config:set EMAIL_PASSWORD="$EMAIL_PASSWORD" --app $APP_NAME
    heroku config:set SMTP_SERVER="smtp.gmail.com" --app $APP_NAME
    heroku config:set SMTP_PORT="587" --app $APP_NAME
fi

# Initialize git if not already done
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit"
fi

# Add Heroku remote
echo "🔗 Adding Heroku remote..."
heroku git:remote -a $APP_NAME

# Deploy to Heroku
echo "🚀 Deploying to Heroku..."
git add .
git commit -m "Deploy caregiver recruitment dashboard"
git push heroku main

# Run database migrations
echo "🗄️ Setting up database..."
heroku run python -c "from app import db; db.create_all()" --app $APP_NAME

# Open the app
echo "🌐 Opening your app..."
heroku open --app $APP_NAME

echo "✅ Deployment complete!"
echo "📱 Your app is available at: https://$APP_NAME.herokuapp.com"
echo ""
echo "📋 Next steps:"
echo "1. Test the upload functionality with the sample data"
echo "2. Configure alert rules in the Alerts tab"
echo "3. Set up email notifications (if not done during deployment)"
echo "4. Customize the dashboard for your team's needs"
echo ""
echo "📁 Sample data is available in: sample_data/sample_leads.zip"
echo "📖 Full documentation is in: README.md"


