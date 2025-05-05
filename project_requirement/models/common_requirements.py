"""
Common constants, fields, and utility functions for requirement management.
This module centralizes all shared code related to requirements, subrequirements.
"""

from datetime import time, datetime

# Constants and Field Definitions

START_WORK_TIME = time(9, 0, 0)  # Start time of business day
END_WORK_TIME = time(18, 0, 0)  # End time of business day
HOURS_PER_DAY = 8  # Standard number of working hours per day

COMPLEXITY_SELECTION = [
    ('none', 'Aucune'),
    ('simple', 'Simple'),
    ('medium', 'Moyenne'),
    ('complex', 'Complexe')
]

COMPLEXITY_TO_DAYS = {
    'none': 0,
    'simple': 3,
    'medium': 9,
    'complex': 10
}

PROJECT_TYPE_SELECTION = [
    ('etude_chiffrage', 'Etude et chiffrage'),
    ('implementation', 'Implémentation'),
]

SUBREQUIREMENT_TYPE_SELECTION = [
    ('interne', 'Interne'),
    ('externe', 'Externe'),
]


# Utility Functions

def get_complexity_from_days(days):
    """Determine complexity level based on estimated days value"""
    if days < 1:
        return 'none'
    elif days <= 3:
        return 'simple'
    elif days <= 9:
        return 'medium'
    else:
        return 'complex'


def get_days_from_complexity(complexity):
    """Convert complexity to estimated days"""
    return COMPLEXITY_TO_DAYS.get(complexity, 0)


def datetime_with_business_hour(date, business_hour):
    """
    Create a datetime object with a specific business hour time component.
    """
    if not date:
        return False

    # Simply combine date with business hour
    return datetime.combine(date, business_hour)
