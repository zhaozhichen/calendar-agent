"""
Initialize test data for the calendar agent system.
"""
from datetime import datetime, timedelta
import random
from typing import List
import logging

from src.api.calendar_client import CalendarClient
from src.constants import BUSINESS_START_HOUR, BUSINESS_END_HOUR

# Test users
TEST_USERS = [
    "alice@example.com",
    "bob@example.com",
    "charlie@example.com",
    "david@example.com",
    "eve@example.com"
]

# Meeting templates
MEETING_TEMPLATES = [
    {
        "title": "Weekly Team Sync",
        "duration_minutes": 60,
        "priority": 3,
        "description": "Regular team sync meeting to discuss progress and blockers",
        "is_recurring": True
    },
    {
        "title": "Project Planning",
        "duration_minutes": 90,
        "priority": 4,
        "description": "Strategic planning session for upcoming project milestones",
        "is_recurring": False
    },
    {
        "title": "Quick Catch-up",
        "duration_minutes": 30,
        "priority": 2,
        "description": "Brief sync to align on specific topics",
        "is_recurring": False
    },
    {
        "title": "Emergency Bug Review",
        "duration_minutes": 45,
        "priority": 5,
        "description": "Urgent meeting to discuss critical bug fixes",
        "is_recurring": False
    },
    {
        "title": "Coffee Chat",
        "duration_minutes": 30,
        "priority": 1,
        "description": "Informal catch-up session",
        "is_recurring": False
    }
]

# Fixed meetings for deterministic testing
FIXED_MEETINGS = [
    # Week 1 - Monday
    {
        "title": "Weekly Team Sync",
        "duration_minutes": 60,
        "priority": 3,
        "description": "Regular team sync meeting to discuss progress and blockers",
        "start_hour": 9,
        "start_minute": 30,
        "organizer": "alice@example.com",
        "attendees": ["bob@example.com", "charlie@example.com"]
    },
    {
        "title": "Project Planning",
        "duration_minutes": 90,
        "priority": 4,
        "description": "Strategic planning session for upcoming project milestones",
        "start_hour": 14,
        "start_minute": 0,
        "organizer": "bob@example.com",
        "attendees": ["alice@example.com", "david@example.com", "eve@example.com"]
    },
    # Week 1 - Tuesday
    {
        "title": "Quick Catch-up",
        "duration_minutes": 30,
        "priority": 2,
        "description": "Brief sync to align on specific topics",
        "start_hour": 10,
        "start_minute": 0,
        "organizer": "charlie@example.com",
        "attendees": ["alice@example.com", "eve@example.com"]
    },
    {
        "title": "Emergency Bug Review",
        "duration_minutes": 45,
        "priority": 5,
        "description": "Urgent meeting to discuss critical bug fixes",
        "start_hour": 15,
        "start_minute": 30,
        "organizer": "david@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "charlie@example.com"]
    },
    # Week 1 - Wednesday
    {
        "title": "Product Strategy",
        "duration_minutes": 60,
        "priority": 4,
        "description": "Discuss product roadmap and strategy",
        "start_hour": 11,
        "start_minute": 0,
        "organizer": "eve@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "david@example.com"]
    },
    {
        "title": "Code Review",
        "duration_minutes": 45,
        "priority": 3,
        "description": "Review pull requests and discuss code quality",
        "start_hour": 14,
        "start_minute": 30,
        "organizer": "bob@example.com",
        "attendees": ["charlie@example.com", "david@example.com"]
    },
    # Week 1 - Thursday
    {
        "title": "Team Building",
        "duration_minutes": 60,
        "priority": 2,
        "description": "Virtual team building activity",
        "start_hour": 10,
        "start_minute": 30,
        "organizer": "alice@example.com",
        "attendees": ["bob@example.com", "charlie@example.com", "david@example.com", "eve@example.com"]
    },
    {
        "title": "Sprint Planning",
        "duration_minutes": 90,
        "priority": 4,
        "description": "Plan next sprint tasks and priorities",
        "start_hour": 13,
        "start_minute": 0,
        "organizer": "charlie@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "david@example.com", "eve@example.com"]
    },
    # Week 1 - Friday
    {
        "title": "Client Meeting",
        "duration_minutes": 60,
        "priority": 5,
        "description": "Important client status update",
        "start_hour": 9,
        "start_minute": 0,
        "organizer": "david@example.com",
        "attendees": ["alice@example.com", "eve@example.com"]
    },
    {
        "title": "Architecture Review",
        "duration_minutes": 90,
        "priority": 4,
        "description": "Review system architecture changes",
        "start_hour": 14,
        "start_minute": 0,
        "organizer": "bob@example.com",
        "attendees": ["alice@example.com", "charlie@example.com", "david@example.com"]
    },
    # Week 2 - Monday
    {
        "title": "Security Review",
        "duration_minutes": 60,
        "priority": 5,
        "description": "Monthly security review meeting",
        "start_hour": 10,
        "start_minute": 0,
        "organizer": "eve@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "charlie@example.com"]
    },
    {
        "title": "Design Review",
        "duration_minutes": 45,
        "priority": 3,
        "description": "Review new feature designs",
        "start_hour": 15,
        "start_minute": 0,
        "organizer": "alice@example.com",
        "attendees": ["bob@example.com", "eve@example.com"]
    },
    # Week 2 - Tuesday
    {
        "title": "Performance Review",
        "duration_minutes": 60,
        "priority": 4,
        "description": "System performance review",
        "start_hour": 11,
        "start_minute": 30,
        "organizer": "charlie@example.com",
        "attendees": ["bob@example.com", "david@example.com", "eve@example.com"]
    },
    {
        "title": "Project Demo",
        "duration_minutes": 60,
        "priority": 3,
        "description": "Demo new features to stakeholders",
        "start_hour": 14,
        "start_minute": 0,
        "organizer": "david@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "charlie@example.com", "eve@example.com"]
    },
    # Week 2 - Wednesday
    {
        "title": "Innovation Workshop",
        "duration_minutes": 90,
        "priority": 2,
        "description": "Brainstorming session for new ideas",
        "start_hour": 9,
        "start_minute": 30,
        "organizer": "bob@example.com",
        "attendees": ["alice@example.com", "charlie@example.com", "eve@example.com"]
    },
    {
        "title": "Documentation Review",
        "duration_minutes": 45,
        "priority": 2,
        "description": "Review and update documentation",
        "start_hour": 13,
        "start_minute": 30,
        "organizer": "eve@example.com",
        "attendees": ["charlie@example.com", "david@example.com"]
    },
    # Week 2 - Thursday
    {
        "title": "Sprint Retrospective",
        "duration_minutes": 60,
        "priority": 3,
        "description": "Review sprint outcomes and lessons learned",
        "start_hour": 10,
        "start_minute": 0,
        "organizer": "alice@example.com",
        "attendees": ["bob@example.com", "charlie@example.com", "david@example.com", "eve@example.com"]
    },
    {
        "title": "Release Planning",
        "duration_minutes": 90,
        "priority": 4,
        "description": "Plan upcoming release schedule",
        "start_hour": 14,
        "start_minute": 30,
        "organizer": "charlie@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "eve@example.com"]
    },
    # Week 2 - Friday
    {
        "title": "Team Social",
        "duration_minutes": 60,
        "priority": 1,
        "description": "Virtual team social gathering",
        "start_hour": 11,
        "start_minute": 0,
        "organizer": "eve@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "charlie@example.com", "david@example.com"]
    },
    {
        "title": "Stakeholder Update",
        "duration_minutes": 45,
        "priority": 5,
        "description": "Update meeting with key stakeholders",
        "start_hour": 15,
        "start_minute": 30,
        "organizer": "david@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "eve@example.com"]
    }
]

def create_test_agents(calendar_client: CalendarClient) -> List[str]:
    """Create test agents for the application.
    
    Args:
        calendar_client: The calendar client to use for creating agents
        
    Returns:
        List of created agent emails
    """
    active_agents = []
    for email in TEST_USERS:
        active_agents.append(email)
        print(f"✓ Created agent for {email}")
    return active_agents

def create_fixed_meetings(calendar_client: CalendarClient, active_agents: List[str]):
    """Create a fixed set of test meetings.
    
    Args:
        calendar_client: The calendar client to use for creating meetings
        active_agents: List of active agent emails
    """
    # Start from today and ensure we start at the beginning of a week (Monday)
    start_date = datetime.now()
    logging.info(f"Initial start_date: {start_date}")
    while start_date.weekday() != 0:  # 0 = Monday
        start_date = start_date + timedelta(days=1)
    
    # Create a mapping of meetings to their business days (0-9 representing the 10 business days)
    meeting_days = {
        # Week 1
        0: [0, 1],         # Monday
        1: [2, 3],         # Tuesday
        2: [4, 5],         # Wednesday
        3: [6, 7],         # Thursday
        4: [8, 9],         # Friday
        # Week 2
        5: [10, 11],       # Monday
        6: [12, 13],       # Tuesday
        7: [14, 15],       # Wednesday
        8: [16, 17],       # Thursday
        9: [18, 19]        # Friday
    }
    
    # Create each fixed meeting
    for day_num, meeting_indices in meeting_days.items():
        # Calculate the actual date (skipping weekends)
        week_number = day_num // 5  # 0 for first week, 1 for second week
        day_in_week = day_num % 5   # 0-4 representing Monday-Friday
        meeting_date = start_date + timedelta(weeks=week_number, days=day_in_week)
        
        for meeting_index in meeting_indices:
            meeting = FIXED_MEETINGS[meeting_index]
            if meeting["organizer"] in active_agents:
                # Set meeting time with the correct date
                meeting_start = meeting_date.replace(
                    hour=meeting["start_hour"],
                    minute=meeting["start_minute"],
                    second=0,
                    microsecond=0
                )
                logging.info(f"Before create_event - meeting_start: {meeting_start}")
                meeting_end = meeting_start + timedelta(minutes=meeting["duration_minutes"])
                logging.info(f"Before create_event - meeting_end: {meeting_end}")
                
                # Ensure organizer is in attendees list
                all_attendees = list(set([meeting["organizer"]] + meeting["attendees"]))
                
                # Create the meeting
                event = calendar_client.create_event(
                    summary=meeting["title"],
                    start_time=meeting_start,
                    end_time=meeting_end,
                    description=meeting["description"],
                    attendees=all_attendees,  # Use the combined list
                    organizer=meeting["organizer"],
                    priority=meeting["priority"]
                )
                print(f"✓ Created fixed meeting: {meeting['title']} (Priority: {meeting['priority']}) ({meeting['organizer']}) on {meeting_start.strftime('%Y-%m-%d %I:%M %p')}")

def create_random_meetings(calendar_client: CalendarClient, active_agents: List[str]):
    """Create random test meetings.
    
    Args:
        calendar_client: The calendar client to use for creating meetings
        active_agents: List of active agent emails
    """
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)  # One month period
    
    logging.info(f"Creating random meetings from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    for day in range(31):  # 0-30 days
        current_date = start_date + timedelta(days=day)
        
        # Skip weekends
        if current_date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            continue
            
        # Create 8 meetings per day between 9 AM and 5 PM
        # Calculate available time slots
        time_slots = []
        for hour in range(9, 17):  # 9 AM to 4 PM (to allow for 1-hour meetings)
            for minute in [0, 15, 30, 45]:
                time_slots.append((hour, minute))
        
        # Randomly select 8 time slots without replacement
        selected_slots = random.sample(time_slots, min(8, len(time_slots)))
        
        for hour, minute in selected_slots:
            # Select random meeting template
            template = random.choice(MEETING_TEMPLATES)
            
            # Select random organizer and attendees
            organizer = random.choice(TEST_USERS)
            num_attendees = random.randint(1, len(TEST_USERS) - 1)
            attendees = random.sample([u for u in TEST_USERS if u != organizer], num_attendees)
            
            # Ensure organizer is in attendees list
            all_attendees = list(set([organizer] + attendees))
            
            # Set meeting time
            meeting_start = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            meeting_end = meeting_start + timedelta(minutes=template["duration_minutes"])
            
            # Ensure meeting doesn't end after 5 PM
            if meeting_end.hour < BUSINESS_END_HOUR or (meeting_end.hour == BUSINESS_END_HOUR and meeting_end.minute == 0):
                # Create the meeting directly
                if organizer in active_agents:
                    event = calendar_client.create_event(
                        summary=template["title"],
                        start_time=meeting_start,
                        end_time=meeting_end,
                        description=template["description"],
                        attendees=all_attendees,  # Use the combined list
                        organizer=organizer,
                        priority=template["priority"]
                    )
                    logging.info(f"Created meeting: {template['title']} (Priority: {template['priority']}) ({organizer}) at {meeting_start.strftime('%Y-%m-%d %I:%M %p')}")

def create_test_data(calendar_client: CalendarClient, use_fixed_meetings: bool = False) -> List[str]:
    """Create all test data for the application.
    
    Args:
        calendar_client: The calendar client to use for creating test data
        use_fixed_meetings: If True, use fixed meeting set; if False, generate random meetings
        
    Returns:
        List of created agent emails
    """
    print("\n=== Creating Test Agents ===")
    active_agents = create_test_agents(calendar_client)
    
    print("\n=== Creating Test Meetings ===")
    logging.info("==================================================")
    logging.info(f"Initialization mode: {'FIXED' if use_fixed_meetings else 'RANDOM'} meetings")
    logging.info("==================================================")
    
    if use_fixed_meetings:
        logging.info("Using fixed meeting schedule")
        create_fixed_meetings(calendar_client, active_agents)
    else:
        logging.info("Using random meeting generation for next 31 days")
        logging.info("Will create 8 meetings per business day")
        create_random_meetings(calendar_client, active_agents)
    
    return active_agents 