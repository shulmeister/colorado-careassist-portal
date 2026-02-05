# Newsletter Templates

## Location

All newsletter templates are in the root directory of this project:

- `newsletter_template_clients.html` - Base template for client newsletters
- `newsletter_template_referral_sources.html` - Base template for referral source newsletters
- `newsletter_january_2025_clients.html` - January 2025 client newsletter (populated)
- `newsletter_january_2025_referral_sources.html` - January 2025 referral source newsletter (populated)

## How to Upload Templates to Brevo

Since Brevo templates are managed through the UI (not API), follow these steps:

### Option 1: Manual Upload via Brevo UI

1. Log in to your Brevo account at https://app.brevo.com
2. Navigate to **Campaigns** > **Templates** > **Email Templates**
3. Click **Create a new template**
4. Choose **Start from scratch** > **HTML custom code**
5. Open one of the template HTML files (e.g., `newsletter_january_2025_clients.html`)
6. Copy the entire HTML content
7. Paste into Brevo's HTML editor
8. Click **Save & Activate**
9. Name it appropriately (e.g., "Client Newsletter - January 2025")

### Option 2: View Templates via API

You can preview templates using the API endpoint:

```
https://portal.coloradocareassist.com/sales/api/brevo/newsletter-template/newsletter_january_2025_clients.html
```

Replace the filename with any of the template files listed above.

### Option 3: Open Locally

Open the HTML files directly in your browser:

```
file:///path/to/sales-dashboard/newsletter_january_2025_clients.html
```

## Template Structure

- **Base Templates**: `newsletter_template_*.html` - Reusable templates with placeholders
- **Populated Templates**: `newsletter_january_2025_*.html` - Ready-to-send versions with January 2025 content

## Using Templates in Newsletter UI

The Newsletter management UI (`/newsletters` route) can load these templates from the codebase and send them via Brevo API. The templates don't need to be uploaded to Brevo's template system to use them for sending - they're served directly from the codebase.

However, if you want them to appear in Brevo's "Saved Templates" list (as shown in your screenshot), you'll need to upload them manually through the UI as described in Option 1.

