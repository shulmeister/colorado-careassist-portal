#!/usr/bin/env python3
"""Test reading Dashboard cells directly"""

import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import json

load_dotenv()

creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(os.getenv('SHEET_ID'))
dashboard_worksheet = spreadsheet.worksheet('Dashboard')

print("B21:", dashboard_worksheet.cell(21, 2).value)
print("B22:", dashboard_worksheet.cell(22, 2).value)
print("B23:", dashboard_worksheet.cell(23, 2).value)
