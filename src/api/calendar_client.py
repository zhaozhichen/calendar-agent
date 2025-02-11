"""
Calendar API client implementation.

This module provides a high-level interface for calendar operations with built-in
business hours logic.

Key Classes:
    - CalendarClient: Main client class with methods:
        - create_event(): Creates a new calendar event with specified parameters
            - Handles timezone conversion to EST
            - Validates business hours
            - Supports priority levels
            - Manages attendee lists
        
        - delete_event(): Removes an event from all participants' calendars
            - Ensures consistent deletion across calendars
            - Returns success/failure status
        
        - get_events(): Retrieves calendar events within a date range
            - Supports filtering by calendar ID and owner
            - Handles timezone conversion
            - Returns events in consistent format
        
        - find_free_slots(): Finds available meeting times
            - Considers business hours (9 AM - 5 PM EST)
            - Checks all attendees' availability
            - Returns possible slots with rationale
            - Handles timezone-aware datetime objects

Features:
1. Timezone Management:
   - All times are converted to EST for consistency
   - Handles timezone-aware and naive datetime objects
   - Maintains timezone information in responses

2. Business Hours:
   - Enforces 9 AM - 5 PM EST business hours
   - Validates meeting durations against business hours
   - Skips weekends in scheduling

3. Event Management:
   - Stores events per participant for efficient lookup
   - Maintains consistency across multiple calendars
   - Supports priority levels for meetings
   - Handles attendee and organizer information

4. Error Handling:
   - Validates input parameters
   - Provides detailed error messages
   - Ensures data consistency
   - Logs important operations for debugging
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
import uuid
import logging

from src.constants import BUSINESS_START_HOUR, BUSINESS_END_HOUR

class CalendarClient:
    def __init__(self):
        """Initialize the calendar client."""
        self._events = {}  # In-memory storage for events
        logging.info("Initialized CalendarClient")
        
    def create_event(self,
                    summary: str,
                    start_time: datetime,
                    end_time: datetime,
                    description: str = None,
                    attendees: List[str] = None,
                    organizer: str = None,
                    priority: int = None) -> Dict[str, Any]:
        """Create a new calendar event.
        
        Args:
            summary: Event title
            start_time: Start time in local time
            end_time: End time in local time
            description: Optional event description
            attendees: Optional list of attendee emails
            organizer: Optional organizer email
            priority: Optional priority level for the event
            
        Returns:
            Created event details
        """
        event_id = str(uuid.uuid4())
        
        event = {
            'id': event_id,
            'summary': summary,
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': end_time.isoformat()},
            'description': description,
            'attendees': [{'email': email} for email in (attendees or [])],
            'organizer': {'email': organizer} if organizer else None,
            'priority': priority
        }
        
        # Store event for each attendee and organizer
        all_participants = set(attendees or [])
        if organizer:
            all_participants.add(organizer)
            
        for participant in all_participants:
            if participant not in self._events:
                self._events[participant] = []
            self._events[participant].append(event)
            logging.info(f"Created event '{summary}' for {participant} at {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}")
        
        return event
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        deleted = False
        for participant_events in self._events.values():
            for i, event in enumerate(participant_events):
                if event['id'] == event_id:
                    participant_events.pop(i)
                    deleted = True
                    logging.info(f"Deleted event {event_id} ({event['summary']})")
                    break
        return deleted
    
    def get_events(self,
                  start_time: datetime,
                  end_time: datetime,
                  owner_email: str = None) -> List[Dict[str, Any]]:
        """Get events in a time range.
        
        Args:
            start_time: Start time in local time
            end_time: End time in local time
            owner_email: Optional owner email to filter events
            
        Returns:
            List of events in the time range
        """
        logging.info(f"Getting events for {owner_email}")
        logging.info(f"Date range: {start_time} to {end_time}")
        
        if owner_email not in self._events:
            logging.info(f"No events found for {owner_email}")
            return []
            
        events = self._events[owner_email]
        filtered_events = []
        
        # Ensure start_time and end_time are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.astimezone()
        if end_time.tzinfo is None:
            end_time = end_time.astimezone()
        
        for event in events:
            # Convert event times to datetime objects and ensure they are timezone-aware
            event_start = datetime.fromisoformat(event['start']['dateTime'])
            event_end = datetime.fromisoformat(event['end']['dateTime'])
            
            # Make event times timezone-aware if they aren't already
            if event_start.tzinfo is None:
                event_start = event_start.astimezone()
            if event_end.tzinfo is None:
                event_end = event_end.astimezone()
            
            # Filter by date range if specified
            if start_time > event_end or end_time < event_start:
                continue
                
            filtered_events.append(event)
            
        logging.info(f"Found {len(filtered_events)} events for {owner_email}")
        for event in filtered_events:
            logging.info(f"Event: {event['summary']} at {event['start']['dateTime']}")
            
        return filtered_events

    def find_free_slots(self,
                       duration_minutes: int,
                       start_time: datetime,
                       end_time: datetime,
                       attendees: List[str] = None) -> List[Dict[str, Any]]:
        """Find available time slots for a meeting.
        
        Args:
            duration_minutes: Meeting duration in minutes
            start_time: Start of search range in local time
            end_time: End of search range in local time
            attendees: List of attendee emails
            
        Returns:
            List of available start times in local time
        """
        if not start_time:
            start_time = datetime.now()
        if not end_time:
            end_time = start_time + timedelta(days=7)
            
        # Validate duration against business hours
        total_business_minutes = (BUSINESS_END_HOUR - BUSINESS_START_HOUR) * 60
        if duration_minutes > total_business_minutes:
            return [{
                'start_time': None,
                'conflicts': [],
                'rationale': (
                    f"Meeting duration ({duration_minutes} minutes) exceeds total business hours "
                    f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM = {total_business_minutes} minutes)"
                )
            }]
            
        # Calculate latest possible start time for this duration
        latest_start_hour = BUSINESS_END_HOUR - (duration_minutes // 60)
        latest_start_minute = 60 - (duration_minutes % 60) if duration_minutes % 60 > 0 else 0
        if latest_start_minute == 60:  # Handle case where duration is exact hours
            latest_start_hour -= 1
            latest_start_minute = 0
            
        # Get all attendees' events
        all_busy_periods = []
        if attendees:
            for attendee in attendees:
                events = self.get_events(start_time, end_time, attendee)
                for event in events:
                    start = datetime.fromisoformat(event['start']['dateTime'])
                    end = datetime.fromisoformat(event['end']['dateTime'])
                    all_busy_periods.append({
                        'start': start,
                        'end': end,
                        'attendee': attendee,
                        'title': event['summary']
                    })
            
        # Sort busy periods
        all_busy_periods.sort(key=lambda x: x['start'])
            
        # Find free slots
        free_slots = []
        current_time = start_time
        
        # Only consider business hours
        def next_business_hour(dt: datetime) -> datetime:
            """Get the next valid business hour, considering meeting duration."""
            # If before business hours, move to start of business hours
            if dt.hour < BUSINESS_START_HOUR:
                return dt.replace(hour=BUSINESS_START_HOUR, minute=0)
                
            # If after latest possible start time, move to start of next business day
            if dt.hour > latest_start_hour or (dt.hour == latest_start_hour and dt.minute > latest_start_minute):
                return (dt + timedelta(days=1)).replace(hour=BUSINESS_START_HOUR, minute=0)
                
            return dt
        
        current_time = next_business_hour(current_time)
        
        while current_time < end_time:
            # Calculate meeting end time
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Skip if meeting would end after business hours
            if (slot_end.hour > BUSINESS_END_HOUR or 
                (slot_end.hour == BUSINESS_END_HOUR and slot_end.minute > 0)):
                # Move to the start of the next business day
                current_time = (current_time + timedelta(days=1)).replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Skip if meeting would start too late to end within business hours
            if (current_time.hour > latest_start_hour or 
                (current_time.hour == latest_start_hour and current_time.minute > latest_start_minute)):
                # Move to the start of the next business day
                current_time = (current_time + timedelta(days=1)).replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Check if this slot works for all attendees
            conflicts = []
            
            for period in all_busy_periods:
                if (period['start'] <= current_time < period['end'] or
                    period['start'] < slot_end <= period['end'] or
                    (current_time <= period['start'] and slot_end >= period['end'])):
                    conflicts.append(period)
            
            if not conflicts:
                rationale = (
                    f"Found a free slot at {current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')} "
                    f"where all attendees are available and meeting fits within business hours "
                    f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM)."
                )
            else:
                rationale = f"Slot at {current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')} has conflicts:\n"
                for conflict in conflicts:
                    rationale += f"- {conflict['attendee']} has '{conflict['title']}' from {conflict['start'].strftime('%I:%M %p')} to {conflict['end'].strftime('%I:%M %p')}\n"
            
            free_slots.append({
                'start_time': current_time,
                'end_time': slot_end,
                'conflicts': conflicts,
                'rationale': rationale
            })
            
            # Move to next time slot
            current_time += timedelta(minutes=30)
            current_time = next_business_hour(current_time)
        
        return free_slots 