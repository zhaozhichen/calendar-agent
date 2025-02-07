"""
Calendar API client implementation.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pytz import timezone
import uuid
import pytz
import functools
import inspect
import os
import sys
import logging

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

from src.constants import EST, BUSINESS_START_HOUR, BUSINESS_END_HOUR

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
            summary: Event title/summary
            start_time: Event start time
            end_time: Event end time
            description: Optional event description
            attendees: Optional list of attendee emails
            organizer: Optional organizer email
            priority: Optional priority level (1-5)
            
        Returns:
            Created event details
        """
        event_id = str(uuid.uuid4())
        
        # Ensure times are in EST timezone
        if start_time.tzinfo != EST:
            start_time = start_time.astimezone(EST)
        if end_time.tzinfo != EST:
            end_time = end_time.astimezone(EST)
            
        event = {
            'id': event_id,
            'summary': summary,
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': end_time.isoformat()},
            'description': description,
            'attendees': [{'email': email} for email in (attendees or [])],
            'organizer': {'email': organizer} if organizer else None,
            'priority': priority  # Store priority in the event
        }
        
        # Store event for each attendee and organizer
        all_participants = set(attendees or [])
        if organizer:
            all_participants.add(organizer)
            
        for participant in all_participants:
            if participant not in self._events:
                self._events[participant] = []
            self._events[participant].append(event)
            logging.info(f"Created event '{summary}' for {participant} at {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} EST")
        
        return event
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event.
        
        Args:
            event_id: ID of the event to delete
            
        Returns:
            True if event was deleted, False if not found
        """
        deleted = False
        # Remove event from all participants' calendars
        for participant_events in self._events.values():
            for i, event in enumerate(participant_events):
                if event['id'] == event_id:
                    participant_events.pop(i)
                    deleted = True
                    logging.info(f"Deleted event {event_id} ({event['summary']})")
                    break
        return deleted
    
    def get_events(self,
                  start_date: datetime = None,
                  end_date: datetime = None,
                  calendar_id: str = 'primary',
                  owner_email: str = None) -> List[Dict[str, Any]]:
        """Get calendar events within the specified date range.
        
        Args:
            start_date: Start of the search range
            end_date: End of the search range
            calendar_id: ID of the calendar to search in
            owner_email: Email of the calendar owner
            
        Returns:
            List of events
        """
        logging.info(f"Getting events for {owner_email}")
        logging.info(f"Date range: {start_date} to {end_date}")
        
        if owner_email not in self._events:
            logging.info(f"No events found for {owner_email}")
            return []
            
        events = self._events[owner_email]
        filtered_events = []
        
        for event in events:
            # Convert event times to timezone-aware datetimes in EST
            event_start = datetime.fromisoformat(event['start']['dateTime'])
            event_end = datetime.fromisoformat(event['end']['dateTime'])
            
            # Ensure event times are timezone-aware
            if event_start.tzinfo is None:
                event_start = EST.localize(event_start)
            else:
                event_start = event_start.astimezone(EST)
                
            if event_end.tzinfo is None:
                event_end = EST.localize(event_end)
            else:
                event_end = event_end.astimezone(EST)
            
            # Update event times
            event['start']['dateTime'] = event_start.isoformat()
            event['end']['dateTime'] = event_end.isoformat()
            
            # Filter by date range if specified
            if start_date and event_end < start_date:
                continue
            if end_date and event_start > end_date:
                continue
                
            filtered_events.append(event)
            
        logging.info(f"Found {len(filtered_events)} events for {owner_email}")
        for event in filtered_events:
            logging.info(f"Event: {event['summary']} at {event['start']['dateTime']}")
            
        return filtered_events

    def find_free_slots(self,
                       duration_minutes: int,
                       start_date: datetime = None,
                       end_date: datetime = None,
                       calendar_id: str = 'primary',
                       attendees: List[str] = None) -> List[Dict[str, Any]]:
        """Find available time slots of specified duration.
        
        Args:
            duration_minutes: Required duration in minutes
            start_date: Start of the search range
            end_date: End of the search range
            calendar_id: ID of the calendar to search in
            attendees: List of attendee emails to check availability for
            
        Returns:
            List of possible start times with rationale
        """
        if not start_date:
            start_date = datetime.now(EST)
        if not end_date:
            end_date = start_date + timedelta(days=7)
            
        # Convert to EST timezone if not already
        if start_date.tzinfo != EST:
            start_date = start_date.astimezone(EST)
        if end_date.tzinfo != EST:
            end_date = end_date.astimezone(EST)
            
        # Validate duration against business hours
        total_business_minutes = (BUSINESS_END_HOUR - BUSINESS_START_HOUR) * 60
        if duration_minutes > total_business_minutes:
            return [{
                'start_time': None,
                'conflicts': [],
                'rationale': (
                    f"Meeting duration ({duration_minutes} minutes) exceeds total business hours "
                    f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM EST = {total_business_minutes} minutes)"
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
                events = self.get_events(start_date, end_date, calendar_id, attendee)
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
        current_time = start_date
        
        # Only consider business hours
        def next_business_hour(dt: datetime) -> datetime:
            """Get the next valid business hour, considering meeting duration."""
            dt = dt.astimezone(EST)
            
            # If before business hours, move to start of business hours
            if dt.hour < BUSINESS_START_HOUR:
                return dt.replace(hour=BUSINESS_START_HOUR, minute=0)
                
            # If after latest possible start time, move to start of next business day
            if dt.hour > latest_start_hour or (dt.hour == latest_start_hour and dt.minute > latest_start_minute):
                return (dt + timedelta(days=1)).replace(hour=BUSINESS_START_HOUR, minute=0)
                
            return dt
        
        current_time = next_business_hour(current_time)
        
        while current_time < end_date:
            # Calculate meeting end time
            slot_end = current_time + timedelta(minutes=duration_minutes)
            slot_end_est = slot_end.astimezone(EST)
            
            # Skip if meeting would end after business hours
            if (slot_end_est.hour > BUSINESS_END_HOUR or 
                (slot_end_est.hour == BUSINESS_END_HOUR and slot_end_est.minute > 0)):
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
                    f"Found a free slot at {current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')} EST "
                    f"where all attendees are available and meeting fits within business hours "
                    f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM EST)."
                )
            else:
                rationale = f"Slot at {current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')} EST has conflicts:\n"
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