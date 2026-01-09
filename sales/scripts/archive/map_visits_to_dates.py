#!/usr/bin/env python3
"""
Map visit row ranges to dates using Daily Summary tab
"""

import os
from dotenv import load_dotenv
from migrate_data import GoogleSheetsMigrator
from datetime import datetime

load_dotenv()

def get_daily_summary_dates():
    """Get all dates from Daily Summary tab"""
    migrator = GoogleSheetsMigrator()
    spreadsheet = migrator.client.open_by_key(migrator.sheet_id)
    
    # Find Daily Summary worksheet
    worksheets = spreadsheet.worksheets()
    daily_summary_worksheet = None
    
    for ws in worksheets:
        if ws.title.lower() in ['daily summary', 'daily', 'summary']:
            daily_summary_worksheet = ws
            break
    
    if not daily_summary_worksheet:
        return []
    
    all_values = daily_summary_worksheet.get_all_values()
    data_rows = all_values[1:] if len(all_values) > 1 else []
    
    dates = []
    for row in data_rows:
        if not row or not row[0]:
            continue
        
        date_str = row[0].strip()
        if date_str:
            try:
                # Try to parse date
                if '/' in date_str:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                elif '-' in date_str:
                    if len(date_str.split('-')[0]) == 4:  # YYYY-MM-DD
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    else:  # MM-DD-YYYY
                        date_obj = datetime.strptime(date_str, '%m-%d-%Y')
                else:
                    continue
                
                dates.append(date_obj.date())
            except:
                continue
    
    return dates

def analyze_visit_ranges():
    """Analyze visit tab to find date ranges"""
    migrator = GoogleSheetsMigrator()
    spreadsheet = migrator.client.open_by_key(migrator.sheet_id)
    
    # Find visits worksheet
    worksheets = spreadsheet.worksheets()
    visits_worksheet = None
    
    possible_names = ['visits', 'tracker', 'visit tracker', 'sales tracker - visits', 'sales tracker']
    for ws in worksheets:
        ws_name_lower = ws.title.lower()
        if ws_name_lower in [name.lower() for name in possible_names] or 'visit' in ws_name_lower:
            visits_worksheet = ws
            break
    
    if not visits_worksheet:
        print("Could not find visits worksheet")
        return
    
    all_values = visits_worksheet.get_all_values()
    data_rows = all_values[1:] if len(all_values) > 1 else []
    
    print(f"Total visit rows: {len(data_rows)}")
    
    # Find ranges where dates start and stop
    # The pattern: rows with dates mark boundaries, rows without dates in between are groups
    ranges = []
    current_group_start = None
    
    for idx, row in enumerate(data_rows):
        row_num = idx + 2  # +2 because row 1 is header, and enumerate starts at 0
        
        # Check if this row has a date
        has_date = False
        date_obj = None
        if len(row) >= 6 and row[5]:
            date_str = row[5].strip()
            if date_str and date_str != "—":
                try:
                    if ' ' in date_str:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    has_date = True
                except:
                    pass
        
        if has_date:
            # This row has a date - it marks a boundary
            if current_group_start is not None:
                # End previous group (no date)
                ranges.append({
                    'start_row': current_group_start,
                    'end_row': row_num - 1,
                    'has_date': False,
                    'count': row_num - current_group_start
                })
                current_group_start = None
            
            # Add this row as a range with date
            ranges.append({
                'start_row': row_num,
                'end_row': row_num,
                'has_date': True,
                'date': date_obj.date() if date_obj else None,
                'count': 1
            })
        else:
            # This row has no date
            if current_group_start is None:
                # Start a new group
                current_group_start = row_num
    
    # Add final group if any
    if current_group_start is not None:
        ranges.append({
            'start_row': current_group_start,
            'end_row': len(data_rows) + 1,
            'has_date': False,
            'count': len(data_rows) + 2 - current_group_start
        })
    
    print(f"\nFound {len(ranges)} date ranges:")
    for r in ranges[:20]:
        print(f"  Rows {r['start_row']}-{r['end_row']}: {'Has date' if r['has_date'] else 'No date'} ({r['count']} visits)")
    
    return ranges

def map_ranges_to_dates():
    """Map visit ranges to dates from Daily Summary"""
    daily_dates = get_daily_summary_dates()
    ranges = analyze_visit_ranges()
    
    print(f"\n{'='*60}")
    print("MAPPING VISIT RANGES TO DATES")
    print(f"{'='*60}")
    print(f"\nDaily Summary has {len(daily_dates)} dates")
    print(f"Visit tab has {len(ranges)} ranges")
    
    # Filter to only ranges without dates
    ranges_without_dates = [r for r in ranges if not r['has_date']]
    ranges_with_dates = [r for r in ranges if r['has_date']]
    
    print(f"Ranges with dates: {len(ranges_with_dates)}")
    print(f"Ranges without dates: {len(ranges_without_dates)}")
    
    # Find the last date from ranges with dates - this tells us where to start mapping
    last_date_with_visit = None
    if ranges_with_dates:
        dates_from_visits = [r['date'] for r in ranges_with_dates if r.get('date')]
        if dates_from_visits:
            last_date_with_visit = max(dates_from_visits)
            print(f"Last date in visits with dates: {last_date_with_visit}")
    
    # Sort daily dates chronologically (oldest first)
    daily_dates_sorted = sorted(daily_dates)
    
    # Find dates after the last date with a visit
    if last_date_with_visit:
        dates_to_map = [d for d in daily_dates_sorted if d > last_date_with_visit]
    else:
        # No dates in visits, use all dates
        dates_to_map = daily_dates_sorted
    
    print(f"Dates available to map (after last visit date): {len(dates_to_map)}")
    
    # Map ranges to dates in chronological order
    date_mapping = {}
    date_idx = 0
    
    for r in ranges_without_dates:
        if date_idx < len(dates_to_map):
            date = dates_to_map[date_idx]
            date_mapping[(r['start_row'], r['end_row'])] = date
            print(f"  Rows {r['start_row']}-{r['end_row']} ({r['count']} visits) → {date}")
            date_idx += 1
    
    return date_mapping

if __name__ == "__main__":
    map_ranges_to_dates()
