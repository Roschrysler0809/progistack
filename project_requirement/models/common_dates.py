"""
Common date validation and manipulation utilities.
This module centralizes date-related functionality used across the application.
"""

from datetime import timedelta
from math import ceil

from dateutil.relativedelta import relativedelta, MO


# Monday-related utility functions

def is_monday(date):
    """Check if a date is a Monday."""
    if not date:
        return True

    if isinstance(date, str):
        from odoo import fields
        date = fields.Date.from_string(date)

    return date.weekday() == 0  # 0 is Monday


def get_last_monday(from_date=None):
    """Get the most recent Monday, including today if it's a Monday."""
    from odoo import fields

    if not from_date:
        from_date = fields.Date.today()
    elif isinstance(from_date, str):
        from_date = fields.Date.from_string(from_date)

    return from_date + relativedelta(weekday=MO(-1))


def get_next_monday(from_date=None):
    """Get the next Monday, including today if it's a Monday."""
    from odoo import fields

    if not from_date:
        from_date = fields.Date.today()
    elif isinstance(from_date, str):
        from_date = fields.Date.from_string(from_date)

    # If today is Monday, return today's date
    if from_date.weekday() == 0:
        return from_date

    # Otherwise, get next Monday
    return from_date + relativedelta(weekday=MO(+1))


def get_monday_of_week(date=None):
    """Get the Monday of the current week for any given date."""
    from odoo import fields

    if not date:
        date = fields.Date.today()
    elif isinstance(date, str):
        date = fields.Date.from_string(date)

    # Calculate days to subtract to reach Monday (0 if already Monday)
    days_to_subtract = date.weekday()
    return date - timedelta(days=days_to_subtract)


# Business day utility functions

def is_business_day(dt):
    """Check if a date is a business day (Monday to Friday)."""
    from odoo import fields

    if not dt:
        return False

    if isinstance(dt, str):
        dt = fields.Date.from_string(dt)

    # 0-4 are Monday to Friday, 5-6 are Saturday and Sunday
    return dt.weekday() < 5


def ensure_business_day(dt):
    """
    Ensure a date is a business day.
    If it's a weekend (Saturday or Sunday), move it to the next Monday.
    If it's already a business day (Monday to Friday), return it unchanged.
    """
    from odoo import fields

    if not dt:
        return dt

    if isinstance(dt, str):
        dt = fields.Date.from_string(dt)

    # If it's Saturday (5) or Sunday (6), move to next Monday
    if dt.weekday() >= 5:  # Weekend
        # Add days needed to reach Monday
        days_to_add = 7 - dt.weekday() if dt.weekday() == 6 else 2
        return dt + timedelta(days=days_to_add)
    return dt


def get_next_business_day(dt):
    """
    Get the next business day after the given date.
    
    - For Monday-Thursday: returns the next day
    - For Friday: returns the following Monday (skipping weekend)
    - For Saturday/Sunday: returns the following Monday
    """
    from odoo import fields

    if not dt:
        return dt

    if isinstance(dt, str):
        dt = fields.Date.from_string(dt)

    # First, always advance one day
    next_dt = dt + timedelta(days=1)

    # If the next day falls on a weekend, skip to Monday
    if next_dt.weekday() >= 5:  # Weekend (5=Sat, 6=Sun)
        # For Saturday (5): add 2 days to reach Monday
        # For Sunday (6): add 1 day to reach Monday (7-6=1)
        days_to_add = 7 - next_dt.weekday() if next_dt.weekday() == 6 else 2
        return next_dt + timedelta(days=days_to_add)

    # Already a business day
    return next_dt


def add_working_days(start_date, working_days):
    """
    Add a specified number of working days to a date, skipping weekends.
    Counts the start date itself as day 1 of work.
    
    Args:
        start_date: The starting date
        working_days: Number of working days to add
        
    Returns:
        date: The date after adding the specified number of working days
    """
    from odoo import fields

    if not start_date:
        return start_date

    if isinstance(start_date, str):
        start_date = fields.Date.from_string(start_date)

    # Handle 0 or negative working days
    if working_days <= 0:
        return start_date

    # Start with the initial date - it counts as day 1
    result_date = start_date
    days_counted = 1

    # Keep adding days until we reach the target working days
    while days_counted < working_days:
        # Move to next day
        result_date += timedelta(days=1)

        # Only count weekdays (Monday to Friday)
        if result_date.weekday() < 5:
            days_counted += 1

    return result_date


def adjust_duration_by_workforce(estimated_work_days, workforce_factor):
    """
    Calculate adjusted duration based on workforce factor.
    Applies the workforce factor to the estimated days and ensures
    the result is a non-negative integer rounded up.
    """
    # Apply workforce factor to duration
    if workforce_factor > 0:
        duration_days = ceil(estimated_work_days / workforce_factor)
    else:
        duration_days = ceil(estimated_work_days)

    # Ensure we have a non-negative duration
    return max(1, duration_days)  # Minimum of 1 day
