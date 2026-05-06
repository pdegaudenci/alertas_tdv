import pandas as pd

def safe_float(value, default=0.0):
    """Safely convert to float."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert to int."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def format_percentage(value):
    """Format value as percentage."""
    try:
        return f"{float(value):.2%}"
    except (ValueError, TypeError):
        return "N/A"

def format_number(value):
    """Format number with commas."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

def truncate_text(text, max_length=50):
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."