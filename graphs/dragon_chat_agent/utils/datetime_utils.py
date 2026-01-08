"""Utilities for date and time formatting."""

from datetime import datetime, timezone


def get_current_zulu_datetime() -> str:
    """
    Get the current date and time in Zulu (UTC) format.
    
    Returns:
        String in format: YYYYMMDDTHHMMSSZ (e.g., "20240115T143022Z")
    """
    now = datetime.now(timezone.utc)
    
    year = now.year
    month = f"{now.month:02d}"
    day = f"{now.day:02d}"
    hours = f"{now.hour:02d}"
    minutes = f"{now.minute:02d}"
    seconds = f"{now.second:02d}"
    
    return f"{year}{month}{day}T{hours}{minutes}{seconds}Z"

