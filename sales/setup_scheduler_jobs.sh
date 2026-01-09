#!/bin/bash
# Setup Heroku Scheduler Jobs

APP_NAME="careassist-tracker"

echo "Setting up scheduled jobs for $APP_NAME..."

# Note: Heroku Scheduler jobs can only be created via the dashboard
# This script opens the dashboard and provides the commands to paste

echo ""
echo "========================================"
echo "HEROKU SCHEDULER SETUP"
echo "========================================"
echo ""
echo "The Heroku Scheduler dashboard should be open in your browser."
echo "If not, go to: https://dashboard.heroku.com/apps/$APP_NAME/scheduler"
echo ""
echo "Create 2 scheduled jobs:"
echo ""
echo "JOB 1: RingCentral Call Sync"
echo "  Command: python -c \"from ringcentral_service import sync_ringcentral_calls_job; sync_ringcentral_calls_job()\""
echo "  Frequency: Every 30 minutes"
echo "  Next Run: (select a time)"
echo ""
echo "JOB 2: Gmail Email Sync"
echo "  Command: python -c \"from gmail_activity_sync import sync_gmail_activities_job; sync_gmail_activities_job()\""
echo "  Frequency: Every 30 minutes"
echo "  Next Run: (select a time)"
echo ""
echo "========================================"
echo ""
echo "Jobs will run automatically once created!"
echo ""

