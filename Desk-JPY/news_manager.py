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
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False, "News Feed Unavailable"
            
        news_data = response.json()
        now_utc = datetime.now(timezone.utc)
        
        for event in news_data:
            # High impact news for our traded USDJPY desk currencies: USD, JPY
            if event.get('impact') == 'High' and event.get('country') in ['USD', 'JPY']:
                event_date_str = event.get('date')
                try:
                    event_time = datetime.fromisoformat(event_date_str)
                    event_time_utc = event_time.astimezone(timezone.utc)
                except Exception:
                    continue

                diff_seconds = (event_time_utc - now_utc).total_seconds()
                diff_mins = diff_seconds / 60.0
                
                if abs(diff_mins) <= buffer_mins:
                    status = "Upcoming" if diff_mins > 0 else "Recent"
                    return True, f"{status} High Impact News: {event.get('title')} ({event.get('country')}) at {event_time_utc.strftime('%H:%M')} UTC"

    except Exception as e:
        print(f"News Filter Error: {e}")
        return False, ""

    return False, ""

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("Fetching external news data...")
    danger, msg = is_in_danger_zone()
    if danger:
        print(f"DANGER ZONE: {msg}")
    else:
        print("Safe to trade (No High-Impact News in buffer).")
