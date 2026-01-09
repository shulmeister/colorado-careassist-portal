import os
import requests

api_key = os.getenv('MAILCHIMP_API_KEY')
server = os.getenv('MAILCHIMP_SERVER_PREFIX')
list_id = os.getenv('MAILCHIMP_LIST_ID')

if not all([api_key, server, list_id]):
    print("Mailchimp not configured")
    exit(1)

base_url = f"https://{server}.api.mailchimp.com/3.0"
headers = {'Authorization': f'Bearer {api_key}'}

# Get segments
print("=== Mailchimp Segments ===")
resp = requests.get(f"{base_url}/lists/{list_id}/segments", headers=headers, params={'count': 100})
if resp.status_code == 200:
    for seg in resp.json().get('segments', []):
        print(f"  {seg['name']}: {seg['member_count']} members")
else:
    print(f"Error: {resp.status_code}")

# Get tags (different from segments)
print()
print("=== Mailchimp Tags ===")
resp = requests.get(f"{base_url}/lists/{list_id}/tag-search", headers=headers)
if resp.status_code == 200:
    for tag in resp.json().get('tags', []):
        print(f"  {tag['name']}: {tag.get('member_count', '?')} members")
else:
    # Try alternate endpoint
    resp = requests.get(f"{base_url}/lists/{list_id}/members?count=1", headers=headers)
    if resp.status_code == 200:
        # Get unique tags from first few members
        resp2 = requests.get(f"{base_url}/lists/{list_id}/members?count=100", headers=headers)
        all_tags = set()
        for m in resp2.json().get('members', []):
            for t in m.get('tags', []):
                all_tags.add(t.get('name', ''))
        print("  (Tags found in sample of members):")
        for t in sorted(all_tags):
            if t:
                print(f"    {t}")
