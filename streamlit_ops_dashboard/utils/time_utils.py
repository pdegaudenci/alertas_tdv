from datetime import datetime, timezone
import pytz

def get_current_utc():
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)

def format_timestamp(ts_str, to_local=True):
    """Format timestamp string to readable format."""
    try:
        if isinstance(ts_str, str):
            # Assume ISO format
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        else:
            dt = ts_str

        if to_local:
            local_tz = pytz.timezone('Europe/Madrid')  # Adjust as needed
            dt = dt.astimezone(local_tz)
            return dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return str(ts_str)

def get_today_date():
    """Get today's date in YYYY-MM-DD format."""
    return get_current_utc().date().isoformat()