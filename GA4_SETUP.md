# GA4 Setup Instructions

## 1. Create Service Account in Google Cloud Console

1. Go to https://console.cloud.google.com
2. Select your project (same one used for OAuth)
3. Navigate to **IAM & Admin** > **Service Accounts**
4. Click **+ CREATE SERVICE ACCOUNT**
5. Fill in:
   - Service account name: `ga4-reader`
   - Service account ID: `ga4-reader`
   - Description: `Read-only access to GA4 for marketing dashboard`
6. Click **CREATE AND CONTINUE**
7. For roles, add: **Viewer** (basic role)
8. Click **CONTINUE** then **DONE**

## 2. Create and Download Key

1. Click on the service account you just created
2. Go to **KEYS** tab
3. Click **ADD KEY** > **Create new key**
4. Choose **JSON** format
5. Click **CREATE** - this downloads the JSON key file

## 3. Add Service Account to GA4

1. Go to Google Analytics: https://analytics.google.com
2. Navigate to **Admin** (bottom left gear icon)
3. Under **Account** column, click **Account Access Management**
4. Click the **+** button then **Add users**
5. Add the service account email (from JSON file, looks like: `ga4-reader@YOUR-PROJECT-ID.iam.gserviceaccount.com`)
6. Assign **Viewer** role
7. Click **Add**

## 4. Set Environment Variable on Heroku

### Option A: Via Heroku Dashboard (Easier)
1. Go to https://dashboard.heroku.com
2. Open your app: `portal-coloradocareassist-3e1a4bb34793`
3. Go to **Settings** tab
4. Click **Reveal Config Vars**
5. Add new config var:
   - Key: `GOOGLE_SERVICE_ACCOUNT_JSON`
   - Value: Copy the ENTIRE contents of the downloaded JSON file (including the curly braces)
6. Click **Add**

### Option B: Via Heroku CLI
```bash
# First, read the JSON file and escape it properly
cat path/to/your-service-account-key.json | jq -c . > temp.json

# Then set it as config var
heroku config:set GOOGLE_SERVICE_ACCOUNT_JSON="$(cat temp.json)" -a portal-coloradocareassist-3e1a4bb34793

# Clean up
rm temp.json
```

## 5. Verify Setup

After setting the environment variable, the app will automatically restart. You can verify GA4 is working by:

1. Visiting: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/test-ga4
2. You should see:
   ```json
   {
     "service_account_configured": true,
     "property_id": "445403783",
     "client_initialized": true,
     "test_query_successful": true,
     "sample_users": [some number]
   }
   ```

## Troubleshooting

If you get permission errors:
1. Make sure the service account email is added to GA4 with Viewer permissions
2. Verify the property ID is correct (currently set to: 445403783)
3. Check that the JSON was copied completely with all special characters

If you need a different property ID:
```bash
heroku config:set GA4_PROPERTY_ID=YOUR_PROPERTY_ID -a portal-coloradocareassist-3e1a4bb34793
```