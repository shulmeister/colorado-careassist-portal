## Recruiter Dashboard – Facebook Lead Intake

The recruiter dashboard can now ingest Meta Lead Ads submissions without leaving
the portal.

### Environment variables

Set these in the `caregiver-lead-tracker` Heroku app (or your `.env` when
developing locally):

| Key | Description |
| --- | --- |
| `FACEBOOK_APP_ID` | Meta app id that has the `leads_retrieval` permission |
| `FACEBOOK_APP_SECRET` | Secret for the app above |
| `FACEBOOK_ACCESS_TOKEN` | Long-lived page token with access to the lead forms |
| `FACEBOOK_AD_ACCOUNT_ID` | Numeric ad account id (no `act_` prefix) |

### Manual pull from the UI

The **Facebook Campaign Management** card now includes a `Pull Leads` button.
Clicking it:

1. Calls `/api/facebook/fetch-leads`
2. Pulls any new submissions from every active lead-gen campaign
3. Drops the leads into the SQL database and refreshes the dashboard

Status text under the buttons shows how many leads were ingested and when the
last pull ran.

### Scheduled pull (recommended)

Use the helper script to keep leads fresh even when nobody presses the button:

```bash
cd /Users/shulmeister/Documents/GitHub/recruiter-dashboard
python fetch_facebook_leads.py
```

For Heroku Scheduler, add a daily job that runs `python fetch_facebook_leads.py`
and the script will log how many leads were imported.

### Duplicate protection

Every Facebook submission carries its native Lead ID. We persist that value in
the `facebook_lead_id` column and skip anything we've already ingested, even if
someone resubmits the same contact info. Existing manual leads get backfilled
with the ID the first time they match by email/phone/name.

