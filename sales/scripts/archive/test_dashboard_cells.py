#!/usr/bin/env python3
"""Test reading Dashboard worksheet cells B21, B22, B23"""

import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import json

load_dotenv()

def test_dashboard_cells():
    """Test reading Dashboard worksheet cells"""
    print("=" * 60)
    print("TESTING DASHBOARD WORKSHEET CELLS")
    print("=" * 60)
    
    try:
        # Get credentials
        creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
        if not creds_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT_KEY not found")
            return
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)
        
        sheet_id = os.getenv('SHEET_ID')
        if not sheet_id:
            print("❌ SHEET_ID not found")
            return
        
        print(f"\n📄 Opening spreadsheet: {sheet_id}")
        spreadsheet = client.open_by_key(sheet_id)
        
        # List all worksheets
        worksheets = spreadsheet.worksheets()
        print(f"\n📋 Available worksheets:")
        for ws in worksheets:
            print(f"   - {ws.title}")
        
        # Find Dashboard worksheet
        dashboard_worksheet = None
        for ws in worksheets:
            if ws.title.lower() == 'dashboard':
                dashboard_worksheet = ws
                break
        
        if not dashboard_worksheet:
            print("\n❌ Dashboard worksheet not found!")
            print("   Trying to find worksheet with 'dashboard' in name...")
            for ws in worksheets:
                if 'dashboard' in ws.title.lower():
                    print(f"   Found similar: '{ws.title}'")
                    dashboard_worksheet = ws
                    break
        
        if not dashboard_worksheet:
            print("\n❌ Could not find Dashboard worksheet")
            return
        
        print(f"\n✅ Found worksheet: '{dashboard_worksheet.title}'")
        
        # Read cells B21, B22, B23
        print("\n📊 Reading cells:")
        print("-" * 60)
        
        try:
            cell_b21 = dashboard_worksheet.cell(21, 2).value  # B21
            print(f"B21 (Total Hours): {cell_b21}")
        except Exception as e:
            print(f"❌ Error reading B21: {e}")
            cell_b21 = None
        
        try:
            cell_b22 = dashboard_worksheet.cell(22, 2).value  # B22
            print(f"B22 (Total Costs): {cell_b22}")
        except Exception as e:
            print(f"❌ Error reading B22: {e}")
            cell_b22 = None
        
        try:
            cell_b23 = dashboard_worksheet.cell(23, 2).value  # B23
            print(f"B23 (Total Bonuses): {cell_b23}")
        except Exception as e:
            print(f"❌ Error reading B23: {e}")
            cell_b23 = None
        
        # Try to parse values
        print("\n💰 Parsed values:")
        print("-" * 60)
        
        if cell_b21:
            try:
                hours = float(str(cell_b21).replace('$', '').replace(',', ''))
                print(f"Total Hours: {hours}")
            except:
                print(f"Total Hours: Could not parse '{cell_b21}'")
        
        if cell_b22:
            try:
                costs = float(str(cell_b22).replace('$', '').replace(',', ''))
                print(f"Total Costs: ${costs:.2f}")
            except:
                print(f"Total Costs: Could not parse '{cell_b22}'")
        
        if cell_b23:
            try:
                bonuses = float(str(cell_b23).replace('$', '').replace(',', ''))
                print(f"Total Bonuses: ${bonuses:.2f}")
            except:
                print(f"Total Bonuses: Could not parse '{cell_b23}'")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_cells()
