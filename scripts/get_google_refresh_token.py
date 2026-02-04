#!/usr/bin/env python3
"""
Generate Google OAuth Refresh Token for Gigi

Run this script ONCE to get a refresh token for Gmail/Calendar access.
The refresh token will be printed - add it to your .env file as:
GOOGLE_WORK_REFRESH_TOKEN=<the token>

Usage:
    python scripts/get_google_refresh_token.py
"""

import os
import sys
from pathlib import Path

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

# Google OAuth settings - use Clawd Desktop client (supports localhost redirects)
# Must be set via environment variable or .env file
CLIENT_ID = os.getenv("GOOGLE_WORK_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_WORK_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: GOOGLE_WORK_CLIENT_ID and GOOGLE_WORK_CLIENT_SECRET must be set")
    print("Set these in your .env file or environment")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",  # Read, send, delete emails
    "https://www.googleapis.com/auth/calendar",  # Full calendar access
    "https://www.googleapis.com/auth/drive",  # Full drive access
]

def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Installing google-auth-oauthlib...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth-oauthlib"])
        from google_auth_oauthlib.flow import InstalledAppFlow

    # Create OAuth config - use loopback for desktop apps
    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "http://127.0.0.1"]
        }
    }

    print("\n" + "="*60)
    print("GOOGLE OAUTH SETUP FOR GIGI")
    print("="*60)
    print("\nThis will open a browser window to authorize Gigi to access:")
    print("  - Gmail (read-only)")
    print("  - Calendar (read-only)")
    print("  - Drive (read-only)")
    print("\nLog in with: jason@coloradocareassist.com")
    print("="*60 + "\n")

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    try:
        # Try to run local server on port 0 (auto-select available port)
        # This works better with Google's loopback redirect
        credentials = flow.run_local_server(port=0, open_browser=True)
    except Exception as e:
        print(f"\nLocal server failed: {e}")
        print("Trying manual authorization flow...")
        # Fallback to console-based flow (copy/paste URL)
        auth_url, _ = flow.authorization_url(prompt='consent')
        print(f"\nOpen this URL in your browser:\n{auth_url}\n")
        code = input("Enter the authorization code: ")
        flow.fetch_token(code=code)
        credentials = flow.credentials

    # Print the refresh token
    print("\n" + "="*60)
    print("SUCCESS! Here's your refresh token:")
    print("="*60)
    print(f"\nGOOGLE_WORK_REFRESH_TOKEN={credentials.refresh_token}")
    print("\n" + "="*60)
    print("\nAdd this to your .env file or ~/.gigi-env on Mac Mini")
    print("="*60 + "\n")

    # Try to update .env file
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        content = env_file.read_text()
        if "GOOGLE_WORK_REFRESH_TOKEN=" in content:
            # Update existing
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith("GOOGLE_WORK_REFRESH_TOKEN=") or line.startswith("# GOOGLE_WORK_REFRESH_TOKEN="):
                    new_lines.append(f"GOOGLE_WORK_REFRESH_TOKEN={credentials.refresh_token}")
                else:
                    new_lines.append(line)
            env_file.write_text('\n'.join(new_lines))
            print(f"Updated {env_file} with refresh token")
        else:
            # Append
            with open(env_file, 'a') as f:
                f.write(f"\nGOOGLE_WORK_REFRESH_TOKEN={credentials.refresh_token}\n")
            print(f"Added refresh token to {env_file}")

if __name__ == "__main__":
    main()
