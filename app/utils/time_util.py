from datetime import datetime, timedelta, timezone
import pytz

__all__ = [
    "get_current_time",
    "get_this_week_time",
    "get_current_date"
]

def get_current_time() -> str:
    now = datetime.now(timezone.utc)
    weekday = now.strftime("%A")            # e.g., "Monday"
    date_str = now.strftime("%B %d, %Y")    # e.g., "May 06, 2025"
    return f"{weekday}, {date_str}"

def get_utc_time_info():
    now = datetime.now(timezone.utc)
    
    day_name = now.strftime("%A")         # e.g., "Monday"
    utc_date = now.strftime("%Y-%m-%d")   # e.g., "2025-05-05"
    utc_time = now.strftime("%H:%M:%S")   # e.g., "13:45:00"

    return {
        "day_name": day_name,
        "utc_date": utc_date,
        "utc_time": utc_time,
    }

def get_this_week_time() -> dict:
    now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))

    monday = now - timedelta(now.weekday() - 0)
    monday = f"ngày {monday.day:02d}/{monday.month:02d}/{monday.year}"

    sunday = now + timedelta(6 - now.weekday())
    sunday = f"ngày {sunday.day:02d}/{sunday.month:02d}/{sunday.year}"
    return {
        "monday": monday,
        "sunday": sunday
    }