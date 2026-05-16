import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

def is_in_danger_zone():
    """
    Checks if the current time is within the buffer zone of a High Impact news event.
    Uses an external web API/feed instead of MT5 Calendar.
    Returns (bool, message)
    """
    enable_filter = os.getenv("ENABLE_NEWS_FILTER", "True") == "True"
    if not enable_filter:
        return False, ""

    buffer_mins = int(os.getenv("NEWS_BUFFER_MINUTES", 30))
    
    try:
        # Fetching a reliable High-Impact news JSON feed
        # We use a public endpoint that aggregates Forex news
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False, "News Feed Unavailable"
            
        news_data = response.json()
        now_utc = datetime.now(timezone.utc)
        
        for event in news_data:
            # We only care about High impact news for major pairs
            if event.get('impact') == 'High' and event.get('country') in ['USD', 'EUR', 'GBP']:
                # The feed provides time in "M-D-YYYY H:MMam/pm" format (usually EST/EDT)
                # But this specific feed (FairEconomy) is already converted to UTC or follows a standard
                # We need to parse it. Format: "2026-05-08T12:30:00-04:00" or similar
                event_date_str = event.get('date')
                
                # Parse ISO format (handling the offset)
                try:
                    # Replace the colon in the timezone offset for older python compatibility if needed
                    # but python 3.7+ fromisoformat handles it.
                    event_time = datetime.fromisoformat(event_date_str)
                    # Ensure it's compared in UTC
                    event_time_utc = event_time.astimezone(timezone.utc)
                except:
                    continue

                # Calculate difference
                diff_seconds = (event_time_utc - now_utc).total_seconds()
                diff_mins = diff_seconds / 60.0
                
                # Danger if event is in the buffer zone (before or after)
                if abs(diff_mins) <= buffer_mins:
                    status = "Upcoming" if diff_mins > 0 else "Recent"
                    return True, f"{status} High Impact News: {event.get('title')} ({event.get('country')}) at {event_time_utc.strftime('%H:%M')} UTC"

    except Exception as e:
        print(f"News Filter Error: {e}")
        return False, ""

    return False, ""

if __name__ == "__main__":
    # Test Logic
    from dotenv import load_dotenv
    load_dotenv()
    print("Fetching external news data...")
    danger, msg = is_in_danger_zone()
    if danger:
        print(f"⚠️ DANGER ZONE: {msg}")
    else:
        print("✅ Safe to trade (No High-Impact News in buffer).")
