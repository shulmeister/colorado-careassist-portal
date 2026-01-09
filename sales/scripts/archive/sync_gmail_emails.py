#!/usr/bin/env python3
"""Sync email count from Gmail API (emails sent in last 7 days) to database"""

import os
from dotenv import load_dotenv
from gmail_service import GmailService
from database import db_manager
from models import EmailCount, Base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

load_dotenv()


def sync_gmail_emails():
    """Pull email counts from Gmail API and save to database"""
    print("=" * 60)
    print("SYNCING EMAIL COUNT FROM GMAIL API")
    print("=" * 60)

    # Ensure tables exist
    Base.metadata.create_all(bind=db_manager.engine)

    Session = sessionmaker(bind=db_manager.engine)
    db = Session()

    try:
        gmail_service = GmailService()

        if not gmail_service.enabled:
            print(
                "❌ Gmail not configured. Set GMAIL_SERVICE_ACCOUNT_EMAIL and GMAIL_SERVICE_ACCOUNT_KEY"
            )
            return

        print(
            f"\n📧 Fetching emails sent in last 7 days for: {', '.join(gmail_service.user_emails)}"
        )
        counts_result = gmail_service.get_emails_sent_last_7_days()
        total_count = counts_result.get("total", 0)
        per_user_counts = counts_result.get("per_user", {})

        print(f"✅ Found {total_count} emails sent in last 7 days")
        for email, count in per_user_counts.items():
            print(f"   • {email}: {count}")

        # Get or create email count record
        email_count = db.query(EmailCount).order_by(EmailCount.updated_at.desc()).first()

        user_summary = ", ".join(
            f"{email} ({count})" for email, count in per_user_counts.items()
        ) or ", ".join(gmail_service.user_emails)

        if not email_count:
            email_count = EmailCount(
                emails_sent_7_days=total_count,
                user_email=user_summary,
                last_synced=datetime.utcnow(),
            )
            db.add(email_count)
            print("\n✅ Created new email count record")
        else:
            email_count.emails_sent_7_days = total_count
            email_count.user_email = user_summary
            email_count.last_synced = datetime.utcnow()
            print("\n✅ Updated existing email count record")

        db.commit()

        print(f"\n✅ Sync complete! Last synced: {email_count.last_synced}")
        print(f"   Emails sent (last 7 days): {total_count}")
        print(f"   Users: {user_summary}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    sync_gmail_emails()
