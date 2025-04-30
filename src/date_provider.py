"""
Centralized date provider for the project.
Allows overriding the current date for testing or simulation.
"""
from datetime import date
import os

# Default current date (set to April 30, 2025 as per user context)
_DEFAULT_DATE = date(2025, 4, 30)

# Internal override (for tests or simulation)
_current_date_override = None

def set_current_date(new_date):
    """Override the current date (for testing/simulation)."""
    global _current_date_override
    _current_date_override = new_date

def get_current_date():
    """Get the current date, using override if set, else environment variable, else default."""
    if _current_date_override:
        return _current_date_override
    env_date = os.getenv("CURRENT_DATE")
    if env_date:
        try:
            y, m, d = map(int, env_date.split("-"))
            return date(y, m, d)
        except Exception:
            pass
    return _DEFAULT_DATE
