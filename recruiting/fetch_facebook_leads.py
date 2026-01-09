#!/usr/bin/env python3
"""
Small helper script that fetches the latest Facebook Lead Ads submissions and
stores them in the recruiter dashboard database. This can be invoked manually
or scheduled via the Heroku Scheduler add-on (recommended cadence: daily).
"""

from datetime import datetime

from app import app, fetch_facebook_leads_enhanced


def main() -> None:
    with app.app_context():
        leads_added = fetch_facebook_leads_enhanced()
        timestamp = datetime.utcnow().isoformat()
        print(f"[{timestamp}] Facebook pull completed — added {leads_added} new lead(s).")


if __name__ == "__main__":
    main()

