#!/usr/bin/env python3
"""
Analyze Call and SMS Volume for Overnight and Weekend Hours

This script analyzes RingCentral call logs and SMS messages to determine:
- Expected call/SMS volume during overnight hours (8 PM - 8 AM Mountain Time)
- Expected call/SMS volume during weekends (Saturday & Sunday)

Used to help determine scheduler coverage needs.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

import requests
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RingCentral credentials
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")

# Timezone for Colorado
MOUNTAIN_TZ = pytz.timezone('America/Denver')

# Time definitions
OVERNIGHT_START_HOUR = 20  # 8 PM
OVERNIGHT_END_HOUR = 8     # 8 AM
WEEKEND_DAYS = [5, 6]      # Saturday = 5, Sunday = 6


class RingCentralAnalyzer:
    """Analyzer for RingCentral call and SMS data."""

    def __init__(self):
        self.access_token = None
        self.token_expires_at = None

    def _get_access_token(self) -> str:
        """Get access token using JWT authentication."""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        if not RINGCENTRAL_JWT_TOKEN or not RINGCENTRAL_CLIENT_SECRET:
            raise Exception("RingCentral credentials not configured")

        response = requests.post(
            f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
            auth=(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET),
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": RINGCENTRAL_JWT_TOKEN
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Auth failed: {response.status_code} - {response.text}")

        data = response.json()
        self.access_token = data["access_token"]
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600) - 60)
        return self.access_token

    def _api_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated API request."""
        token = self._get_access_token()
        response = requests.get(
            f"{RINGCENTRAL_SERVER}/restapi/v1.0{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"API error: {response.status_code} - {response.text[:500]}")
            return {}

    def get_call_logs(self, days_back: int = 90) -> List[Dict]:
        """Fetch call logs for the specified period."""
        all_records = []
        date_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Paginate through results
        page = 1
        while True:
            params = {
                "dateFrom": date_from,
                "view": "Detailed",
                "perPage": 250,
                "page": page
            }

            result = self._api_request("/account/~/call-log", params)
            records = result.get("records", [])

            if not records:
                break

            all_records.extend(records)
            logger.info(f"Fetched page {page}: {len(records)} calls (total: {len(all_records)})")

            # Check if there are more pages
            paging = result.get("paging", {})
            if page >= paging.get("totalPages", 1):
                break
            page += 1

        logger.info(f"Total call logs fetched: {len(all_records)}")
        return all_records

    def get_sms_messages(self, days_back: int = 90) -> List[Dict]:
        """Fetch SMS messages for the specified period."""
        all_records = []
        date_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

        page = 1
        while True:
            params = {
                "dateFrom": date_from,
                "messageType": "SMS",
                "perPage": 250,
                "page": page
            }

            result = self._api_request("/account/~/extension/~/message-store", params)
            records = result.get("records", [])

            if not records:
                break

            all_records.extend(records)
            logger.info(f"Fetched page {page}: {len(records)} SMS (total: {len(all_records)})")

            paging = result.get("paging", {})
            if page >= paging.get("totalPages", 1):
                break
            page += 1

        logger.info(f"Total SMS messages fetched: {len(all_records)}")
        return all_records

    def is_overnight(self, dt: datetime) -> bool:
        """Check if datetime is during overnight hours (8 PM - 8 AM Mountain)."""
        mountain_dt = dt.astimezone(MOUNTAIN_TZ) if dt.tzinfo else MOUNTAIN_TZ.localize(dt)
        hour = mountain_dt.hour
        return hour >= OVERNIGHT_START_HOUR or hour < OVERNIGHT_END_HOUR

    def is_weekend(self, dt: datetime) -> bool:
        """Check if datetime is on a weekend."""
        mountain_dt = dt.astimezone(MOUNTAIN_TZ) if dt.tzinfo else MOUNTAIN_TZ.localize(dt)
        return mountain_dt.weekday() in WEEKEND_DAYS

    def parse_datetime(self, dt_str: str) -> datetime:
        """Parse RingCentral datetime string."""
        # Handle various formats
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"]:
            try:
                dt = datetime.strptime(dt_str, fmt)
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)
                return dt
            except ValueError:
                continue
        # Fallback - try ISO format
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

    def analyze_interactions(self, calls: List[Dict], sms_messages: List[Dict]) -> Dict[str, Any]:
        """
        Analyze call and SMS volume by time period.

        Returns comprehensive statistics about overnight and weekend volume.
        """
        # Initialize counters
        stats = {
            "analysis_period_days": 0,
            "total_calls": len(calls),
            "total_sms": len(sms_messages),
            "total_interactions": len(calls) + len(sms_messages),

            # Overall breakdown
            "calls_inbound": 0,
            "calls_outbound": 0,
            "sms_inbound": 0,
            "sms_outbound": 0,

            # Overnight stats
            "overnight_calls": 0,
            "overnight_sms": 0,
            "overnight_calls_inbound": 0,
            "overnight_calls_outbound": 0,
            "overnight_sms_inbound": 0,
            "overnight_sms_outbound": 0,

            # Weekend stats (all day, not just overnight)
            "weekend_calls": 0,
            "weekend_sms": 0,
            "weekend_calls_inbound": 0,
            "weekend_calls_outbound": 0,
            "weekend_sms_inbound": 0,
            "weekend_sms_outbound": 0,

            # Weekend overnight (overlap)
            "weekend_overnight_calls": 0,
            "weekend_overnight_sms": 0,

            # Hourly distribution
            "calls_by_hour": defaultdict(int),
            "sms_by_hour": defaultdict(int),

            # Day of week distribution
            "calls_by_day": defaultdict(int),
            "sms_by_day": defaultdict(int),

            # Daily averages
            "dates_with_data": set()
        }

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Process calls
        for call in calls:
            try:
                start_time = call.get("startTime")
                if not start_time:
                    continue

                dt = self.parse_datetime(start_time)
                mountain_dt = dt.astimezone(MOUNTAIN_TZ)

                direction = call.get("direction", "").lower()
                is_inbound = direction == "inbound"
                is_overnight = self.is_overnight(dt)
                is_weekend_day = self.is_weekend(dt)

                # Count direction
                if is_inbound:
                    stats["calls_inbound"] += 1
                else:
                    stats["calls_outbound"] += 1

                # Count overnight
                if is_overnight:
                    stats["overnight_calls"] += 1
                    if is_inbound:
                        stats["overnight_calls_inbound"] += 1
                    else:
                        stats["overnight_calls_outbound"] += 1

                # Count weekend
                if is_weekend_day:
                    stats["weekend_calls"] += 1
                    if is_inbound:
                        stats["weekend_calls_inbound"] += 1
                    else:
                        stats["weekend_calls_outbound"] += 1

                    if is_overnight:
                        stats["weekend_overnight_calls"] += 1

                # Hourly and daily distribution
                stats["calls_by_hour"][mountain_dt.hour] += 1
                stats["calls_by_day"][day_names[mountain_dt.weekday()]] += 1
                stats["dates_with_data"].add(mountain_dt.date())

            except Exception as e:
                logger.warning(f"Error processing call: {e}")
                continue

        # Process SMS messages
        for msg in sms_messages:
            try:
                created_time = msg.get("creationTime") or msg.get("lastModifiedTime")
                if not created_time:
                    continue

                dt = self.parse_datetime(created_time)
                mountain_dt = dt.astimezone(MOUNTAIN_TZ)

                direction = msg.get("direction", "").lower()
                is_inbound = direction == "inbound"
                is_overnight = self.is_overnight(dt)
                is_weekend_day = self.is_weekend(dt)

                # Count direction
                if is_inbound:
                    stats["sms_inbound"] += 1
                else:
                    stats["sms_outbound"] += 1

                # Count overnight
                if is_overnight:
                    stats["overnight_sms"] += 1
                    if is_inbound:
                        stats["overnight_sms_inbound"] += 1
                    else:
                        stats["overnight_sms_outbound"] += 1

                # Count weekend
                if is_weekend_day:
                    stats["weekend_sms"] += 1
                    if is_inbound:
                        stats["weekend_sms_inbound"] += 1
                    else:
                        stats["weekend_sms_outbound"] += 1

                    if is_overnight:
                        stats["weekend_overnight_sms"] += 1

                # Hourly and daily distribution
                stats["sms_by_hour"][mountain_dt.hour] += 1
                stats["sms_by_day"][day_names[mountain_dt.weekday()]] += 1
                stats["dates_with_data"].add(mountain_dt.date())

            except Exception as e:
                logger.warning(f"Error processing SMS: {e}")
                continue

        # Calculate period and averages
        if stats["dates_with_data"]:
            min_date = min(stats["dates_with_data"])
            max_date = max(stats["dates_with_data"])
            stats["analysis_period_days"] = (max_date - min_date).days + 1
            stats["analysis_start_date"] = min_date.isoformat()
            stats["analysis_end_date"] = max_date.isoformat()

        # Convert sets/defaultdicts for JSON serialization
        stats["dates_with_data"] = len(stats["dates_with_data"])
        stats["calls_by_hour"] = dict(stats["calls_by_hour"])
        stats["sms_by_hour"] = dict(stats["sms_by_hour"])
        stats["calls_by_day"] = dict(stats["calls_by_day"])
        stats["sms_by_day"] = dict(stats["sms_by_day"])

        return stats

    def generate_report(self, stats: Dict[str, Any]) -> str:
        """Generate a human-readable report from the statistics."""
        days = stats.get("analysis_period_days", 1) or 1
        weeks = days / 7

        # Calculate averages
        overnight_calls_per_night = stats["overnight_calls"] / days if days else 0
        overnight_sms_per_night = stats["overnight_sms"] / days if days else 0
        overnight_total_per_night = overnight_calls_per_night + overnight_sms_per_night

        weekend_calls_per_weekend = stats["weekend_calls"] / (weeks * 2) if weeks else 0
        weekend_sms_per_weekend = stats["weekend_sms"] / (weeks * 2) if weeks else 0
        weekend_total_per_weekend_day = weekend_calls_per_weekend + weekend_sms_per_weekend

        # Inbound-specific averages (what actually needs coverage)
        overnight_inbound_calls_per_night = stats["overnight_calls_inbound"] / days if days else 0
        overnight_inbound_sms_per_night = stats["overnight_sms_inbound"] / days if days else 0
        overnight_inbound_total = overnight_inbound_calls_per_night + overnight_inbound_sms_per_night

        weekend_inbound_calls_per_day = stats["weekend_calls_inbound"] / (weeks * 2) if weeks else 0
        weekend_inbound_sms_per_day = stats["weekend_sms_inbound"] / (weeks * 2) if weeks else 0
        weekend_inbound_total = weekend_inbound_calls_per_day + weekend_inbound_sms_per_day

        report = f"""
================================================================================
     COLORADO CAREASSIST - CALL & SMS VOLUME ANALYSIS
     For Scheduler Coverage Planning
================================================================================

ANALYSIS PERIOD: {stats.get('analysis_start_date', 'N/A')} to {stats.get('analysis_end_date', 'N/A')}
                 ({days} days / {weeks:.1f} weeks)

--------------------------------------------------------------------------------
OVERALL STATISTICS
--------------------------------------------------------------------------------
Total Interactions:     {stats['total_interactions']:,}
  - Phone Calls:        {stats['total_calls']:,} ({stats['calls_inbound']:,} inbound, {stats['calls_outbound']:,} outbound)
  - Text Messages:      {stats['total_sms']:,} ({stats['sms_inbound']:,} inbound, {stats['sms_outbound']:,} outbound)

Daily Averages:
  - Calls per day:      {stats['total_calls']/days:.1f}
  - SMS per day:        {stats['total_sms']/days:.1f}
  - Total per day:      {stats['total_interactions']/days:.1f}

--------------------------------------------------------------------------------
OVERNIGHT HOURS (8 PM - 8 AM Mountain Time)
--------------------------------------------------------------------------------
Total Overnight Interactions: {stats['overnight_calls'] + stats['overnight_sms']:,}
  - Overnight Calls:    {stats['overnight_calls']:,} ({stats['overnight_calls_inbound']:,} inbound, {stats['overnight_calls_outbound']:,} outbound)
  - Overnight SMS:      {stats['overnight_sms']:,} ({stats['overnight_sms_inbound']:,} inbound, {stats['overnight_sms_outbound']:,} outbound)

Average per Night:
  - Calls:              {overnight_calls_per_night:.2f}
  - SMS:                {overnight_sms_per_night:.2f}
  - Total:              {overnight_total_per_night:.2f}

>>> INBOUND ONLY (requires response/coverage):
    - Inbound calls per night:  {overnight_inbound_calls_per_night:.2f}
    - Inbound SMS per night:    {overnight_inbound_sms_per_night:.2f}
    - TOTAL INBOUND per night:  {overnight_inbound_total:.2f}

--------------------------------------------------------------------------------
WEEKEND HOURS (Saturday & Sunday - All Day)
--------------------------------------------------------------------------------
Total Weekend Interactions: {stats['weekend_calls'] + stats['weekend_sms']:,}
  - Weekend Calls:      {stats['weekend_calls']:,} ({stats['weekend_calls_inbound']:,} inbound, {stats['weekend_calls_outbound']:,} outbound)
  - Weekend SMS:        {stats['weekend_sms']:,} ({stats['weekend_sms_inbound']:,} inbound, {stats['weekend_sms_outbound']:,} outbound)

Average per Weekend Day (Sat or Sun):
  - Calls:              {weekend_calls_per_weekend:.2f}
  - SMS:                {weekend_sms_per_weekend:.2f}
  - Total:              {weekend_total_per_weekend_day:.2f}

>>> INBOUND ONLY (requires response/coverage):
    - Inbound calls per weekend day:  {weekend_inbound_calls_per_day:.2f}
    - Inbound SMS per weekend day:    {weekend_inbound_sms_per_day:.2f}
    - TOTAL INBOUND per weekend day:  {weekend_inbound_total:.2f}

--------------------------------------------------------------------------------
WEEKEND + OVERNIGHT OVERLAP
--------------------------------------------------------------------------------
Weekend Overnight Calls:    {stats['weekend_overnight_calls']:,}
Weekend Overnight SMS:      {stats['weekend_overnight_sms']:,}
Weekend Overnight Total:    {stats['weekend_overnight_calls'] + stats['weekend_overnight_sms']:,}

--------------------------------------------------------------------------------
HOURLY DISTRIBUTION (Mountain Time)
--------------------------------------------------------------------------------
"""
        # Add hourly breakdown
        for hour in range(24):
            calls = stats['calls_by_hour'].get(hour, 0)
            sms = stats['sms_by_hour'].get(hour, 0)
            total = calls + sms
            bar = "█" * min(int(total / max(1, days) * 10), 50)
            time_label = f"{hour:02d}:00-{hour:02d}:59"
            overnight_marker = " *" if hour >= OVERNIGHT_START_HOUR or hour < OVERNIGHT_END_HOUR else ""
            report += f"  {time_label}: {bar} ({calls} calls, {sms} SMS){overnight_marker}\n"

        report += "\n  (* = overnight hours)\n"

        report += """
--------------------------------------------------------------------------------
DAY OF WEEK DISTRIBUTION
--------------------------------------------------------------------------------
"""
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in day_order:
            calls = stats['calls_by_day'].get(day, 0)
            sms = stats['sms_by_day'].get(day, 0)
            total = calls + sms
            bar = "█" * min(int(total / max(1, weeks) * 2), 50)
            weekend_marker = " **" if day in ["Saturday", "Sunday"] else ""
            report += f"  {day:12s}: {bar} ({calls} calls, {sms} SMS){weekend_marker}\n"

        report += "\n  (** = weekend)\n"

        report += f"""
================================================================================
RECOMMENDATIONS FOR SCHEDULER PROVIDER
================================================================================

Based on the data above:

OVERNIGHT COVERAGE (8 PM - 8 AM):
- Expected INBOUND interactions per night: ~{overnight_inbound_total:.1f}
- This represents {(stats['overnight_calls_inbound'] + stats['overnight_sms_inbound']) / max(1, stats['calls_inbound'] + stats['sms_inbound']) * 100:.1f}% of all inbound traffic

WEEKEND COVERAGE (Saturday & Sunday):
- Expected INBOUND interactions per weekend day: ~{weekend_inbound_total:.1f}
- Total weekend inbound per week: ~{weekend_inbound_total * 2:.1f}

COMBINED AFTER-HOURS (Overnight + Weekend):
- The weekend-overnight overlap accounts for {stats['weekend_overnight_calls'] + stats['weekend_overnight_sms']:,} interactions

COVERAGE MODEL RECOMMENDATION:
"""

        # Provide recommendation based on volume
        total_after_hours_inbound = (
            stats['overnight_calls_inbound'] + stats['overnight_sms_inbound'] +
            stats['weekend_calls_inbound'] + stats['weekend_sms_inbound']
        )

        if overnight_inbound_total < 5 and weekend_inbound_total < 10:
            report += """- SHARED/FRACTIONAL MODEL appears suitable
- Low volume suggests a shared resource with other clients would be cost-effective
- Consider on-call coverage with reasonable response time SLAs
"""
        elif overnight_inbound_total < 15 and weekend_inbound_total < 25:
            report += """- HYBRID MODEL may be optimal
- Moderate volume suggests dedicated overnight coverage with shared weekend coverage
- Or shared overnight with more robust weekend staffing
"""
        else:
            report += """- DEDICATED COVERAGE may be warranted
- Higher volume suggests dedicated after-hours staffing would provide better service
- Consider response time requirements for urgent calls
"""

        report += f"""
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
"""
        return report


def main():
    """Main entry point."""
    print("Starting RingCentral Call/SMS Volume Analysis...")
    print("=" * 60)

    # Check credentials
    if not RINGCENTRAL_CLIENT_ID or not RINGCENTRAL_CLIENT_SECRET or not RINGCENTRAL_JWT_TOKEN:
        print("\nERROR: RingCentral credentials not configured.")
        print("Required environment variables:")
        print("  - RINGCENTRAL_CLIENT_ID")
        print("  - RINGCENTRAL_CLIENT_SECRET")
        print("  - RINGCENTRAL_JWT_TOKEN")
        sys.exit(1)

    analyzer = RingCentralAnalyzer()

    # Fetch data (90 days by default)
    days_back = int(os.getenv("ANALYSIS_DAYS", 90))
    print(f"\nFetching data for the last {days_back} days...")

    try:
        calls = analyzer.get_call_logs(days_back)
        sms_messages = analyzer.get_sms_messages(days_back)
    except Exception as e:
        print(f"\nERROR fetching data: {e}")
        sys.exit(1)

    # Analyze
    print("\nAnalyzing interaction patterns...")
    stats = analyzer.analyze_interactions(calls, sms_messages)

    # Generate and print report
    report = analyzer.generate_report(stats)
    print(report)

    # Save raw stats to JSON for further analysis
    output_file = f"volume_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"\nRaw statistics saved to: {output_file}")


if __name__ == "__main__":
    main()
