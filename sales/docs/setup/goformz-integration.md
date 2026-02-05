# GoFormz to Brevo Integration Setup

This integration automatically adds new customers to Brevo's Client list when they complete a "Client Packet" in GoFormz. This triggers your existing Brevo welcome email automation.

## How It Works

1. **Client completes Client Packet in GoFormz** → 
2. **GoFormz webhook calls our endpoint** (or we poll for new completions) →
3. **Customer added to Brevo Client list** →
4. **Brevo automation sends welcome email** ✨

## Setup Options

### Option 1: Webhook (Real-time, Recommended)

If GoFormz supports webhooks, set up a webhook to call our endpoint when a Client Packet is completed:

**Webhook URL:**
```
https://portal.coloradocareassist.com/sales/api/goformz/webhook
```

**Webhook Configuration in GoFormz:**
1. Go to your GoFormz account settings
2. Navigate to **Integrations** or **Webhooks**
3. Create a new webhook:
   - **URL**: `https://portal.coloradocareassist.com/sales/api/goformz/webhook`
   - **Event**: Form completion / Form submitted
   - **Form**: Client Packet (or filter for forms containing "Client Packet" in the name)
   - **Method**: POST
   - **Format**: JSON

The webhook will automatically:
- Extract customer email, name, and other data from the submission
- Add them to Brevo as a contact
- Add them to the "Client" list (which triggers your welcome automation)

### Option 2: Polling Script (If Webhooks Not Available)

If GoFormz doesn't support webhooks, we can run a scheduled sync script that checks for new completed Client Packets:

**Manual Sync:**
```bash
mac-mini run "python3 sync_goformz_to_brevo.py" -a careassist-tracker
```

**Scheduled Sync (Mac Mini Scheduler):**
1. Go to Mac Mini Dashboard → careassist-tracker → **Resources**
2. Add **Mac Mini Scheduler** addon
3. Create a new job:
   - **Command**: `python3 sync_goformz_to_brevo.py`
   - **Frequency**: Every 10 minutes (or hourly)

**Or via API endpoint:**
```bash
curl -X POST https://portal.coloradocareassist.com/sales/api/goformz/sync-to-brevo?since_hours=24 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing

### Test GoFormz Connection
```bash
mac-mini run "python3 -c 'from goformz_service import GoFormzService; g = GoFormzService(); print(g.test_connection())'" -a careassist-tracker
```

### Test Sync (Dry Run)
```bash
mac-mini run "python3 sync_goformz_to_brevo.py --since-hours 24" -a careassist-tracker
```

### Test Webhook Endpoint
```bash
curl -X POST https://portal.coloradocareassist.com/sales/api/goformz/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "completed",
    "formName": "Client Packet",
    "submissionId": "test123",
    "data": {
      "email": "test@example.com",
      "first_name": "Test",
      "last_name": "User"
    }
  }'
```

## Data Mapping

The integration extracts the following fields from GoFormz submissions:

| GoFormz Field | Brevo Field | Notes |
|--------------|-------------|-------|
| `email` / `Email` / `email_address` | `EMAIL` | Required |
| `first_name` / `First Name` / `firstName` | `FIRSTNAME` | |
| `last_name` / `Last Name` / `lastName` | `LASTNAME` | |
| `phone` / `Phone` / `phone_number` | `SMS` | |
| `address` / `Address` | Custom attribute | |

If a field isn't found, the script will try common variations.

## Troubleshooting

### "GoFormz not configured"
- Check that `GOFORMZ_CLIENT_ID` and `GOFORMZ_CLIENT_SECRET` are set on Mac Mini:
  ```bash
  # Check ~/.gigi-env -a careassist-tracker | grep GOFORMZ
  ```

### "Failed to get token"
- Verify your GoFormz API credentials are correct
- Check if GoFormz API requires a different authentication method
- Contact GoFormz support for API documentation

### "No Client Packet forms found"
- Ensure your form is named "Client Packet" (case-insensitive)
- Or modify `get_completed_client_packets()` in `goformz_service.py` to match your form name

### "Contact added but not to Client list"
- Check that a "Client" list exists in Brevo
- Verify the list name doesn't contain "Referral" (script filters those out)

## Next Steps

1. **Set up webhook in GoFormz** (if available) OR **schedule polling script**
2. **Test with a real Client Packet completion**
3. **Verify welcome email is sent** from Brevo automation
4. **Monitor logs** for any issues:
   ```bash
   tail -f ~/logs/gigi-unified.log -a careassist-tracker | grep goformz
   ```

## Notes

- The integration only processes forms with "Client Packet" in the name
- Customers are only added if they have a valid email address
- Duplicate emails are handled (existing contacts are updated, not duplicated)
- The integration respects rate limits and includes error handling

