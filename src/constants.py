"""
Constants used throughout the calendar agent application.
"""
import pytz

# Timezone configuration
EST = pytz.timezone('America/New_York')

# Business hours configuration (in EST)
BUSINESS_START_HOUR = 9  # 9 AM EST
BUSINESS_END_HOUR = 17   # 5 PM EST 