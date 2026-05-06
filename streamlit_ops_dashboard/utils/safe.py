import logging

logger = logging.getLogger(__name__)

def safe_get(data, key, default=None):
    """Safely get value from dict."""
    try:
        return data.get(key, default) if data else default
    except Exception as e:
        logger.error(f"Error getting key {key}: {e}")
        return default

def safe_list(data):
    """Ensure data is a list."""
    if isinstance(data, list):
        return data
    elif data:
        return [data]
    else:
        return []

def safe_dict(data):
    """Ensure data is a dict."""
    return data if isinstance(data, dict) else {}

def handle_service_error(service_name, error):
    """Handle service errors consistently."""
    logger.error(f"Service {service_name} error: {error}")
    return {'status': 'ERROR', 'error': str(error)}