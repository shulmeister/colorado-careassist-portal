import os
import sys
from google_service import google_service

def test():
    print("--- Testing Gmail Search ---")
    emails = google_service.search_emails(max_results=3)
    if emails:
        for e in emails:
            print(f"From: {e['from']}\nSubject: {e['subject']}\nSnippet: {e['snippet'][:100]}\n---")
    else:
        print("No emails found or error occurred.")

    print("\n--- Testing Calendar ---")
    events = google_service.get_calendar_events(days=7)
    if events:
        for ev in events:
            print(f"Event: {ev['summary']}\nStart: {ev['start']}\n---")
    else:
        print("No calendar events found or error occurred.")

if __name__ == "__main__":
    test()
