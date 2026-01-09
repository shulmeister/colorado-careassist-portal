#!/bin/bash
# Gmail API Setup Script for Heroku

echo "=========================================="
echo "Gmail API Setup for Sales Dashboard"
echo "=========================================="
echo ""

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI not found. Please install it first:"
    echo "   https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

echo "Step 1: Setting up Heroku environment variables"
echo "=========================================="
echo ""
echo "You need to provide the following:"
echo "1. Service Account Email (you provided): github@marketing-dashboard-463608.iam.gserviceaccount.com"
echo "2. Service Account JSON Key (full JSON from Google Cloud Console)"
echo "3. User Email (default: maryssa@coloradocareassist.com)"
echo ""

read -p "Enter the full Service Account JSON Key (paste it here, it's ok if it's long): " json_key
read -p "Enter user email to impersonate [maryssa@coloradocareassist.com]: " user_email
user_email=${user_email:-maryssa@coloradocareassist.com}

echo ""
echo "Setting Heroku config variables..."

# Set the environment variables
heroku config:set GMAIL_SERVICE_ACCOUNT_EMAIL="github@marketing-dashboard-463608.iam.gserviceaccount.com"
heroku config:set GMAIL_SERVICE_ACCOUNT_KEY="$json_key"
heroku config:set GMAIL_USER_EMAIL="$user_email"

echo ""
echo "✅ Environment variables set!"
echo ""
echo "Step 2: Testing Gmail connection"
echo "=========================================="
echo ""
echo "Testing connection..."
heroku run python3 sync_gmail_emails.py

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Make sure domain-wide delegation is configured in Google Admin Console"
echo "   - Client ID: 107287022993112478696"
echo "   - Scope: https://www.googleapis.com/auth/gmail.readonly"
echo ""
echo "2. The dashboard will now show 'Emails Sent - Last 7 Days' KPI"
echo ""
echo "3. To sync emails manually, run: heroku run python3 sync_gmail_emails.py"
