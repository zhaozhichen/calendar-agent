"""
Base agent class for calendar coordination.

This module implements the core calendar agent functionality for intelligent meeting scheduling.

Key Classes:
    - MeetingRequest: Data class representing a meeting request with properties:
        - title: Meeting title
        - duration_minutes: Length of meeting
        - organizer: Email of meeting organizer
        - attendees: List of attendee emails
        - priority: Meeting priority (1-5)
        - preferred_time_ranges: Optional preferred time slots
        - description: Optional meeting description

    - MeetingProposal: Data class representing a proposed meeting solution with properties:
        - request: Original MeetingRequest
        - proposed_start_time: Suggested meeting time
        - conflicts: List of conflicting events that need to be moved
        - affected_attendees: List of people affected by moves
        - impact_score: Numerical score of scheduling impact

    - CalendarAgent: Main agent class with methods:
        - evaluate_meeting_priority(): Assigns priority (1-5) to meetings based on various factors
        - find_meeting_slots(): Finds possible meeting times considering conflicts
        - negotiate_meeting_time(): Handles rescheduling of conflicting meetings
        - _prepare_moved_events(): Internal method to prepare rescheduling plan
        - _delete_conflict(): Internal method to remove conflicting events
        - _create_new_meeting(): Internal method to create the new meeting
        - _create_rescheduled_events(): Internal method to recreate moved meetings

The agent uses a sophisticated algorithm to:
1. Evaluate meeting priorities based on attendees, title keywords, and meeting type
2. Find available time slots considering all attendees' calendars
3. Handle conflicts through priority-based negotiation
4. Generate and execute rescheduling proposals when needed
5. Maintain calendar consistency throughout the process
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import os
import sys
import logging

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

from src.api.calendar_client import CalendarClient
from src.constants import BUSINESS_START_HOUR, BUSINESS_END_HOUR

@dataclass
class MeetingRequest:
    """Data class for meeting requests."""
    title: str
    duration_minutes: int
    organizer: str
    attendees: List[str]
    priority: int  # 1-5, where 5 is highest priority
    preferred_time_ranges: Optional[List[Tuple[datetime, datetime]]] = None
    description: Optional[str] = None

@dataclass
class MeetingProposal:
    """Data class for meeting proposals."""
    request: MeetingRequest
    proposed_start_time: datetime
    conflicts: List[Dict[str, Any]]  # List of conflicting events that need to be moved
    affected_attendees: List[str]
    impact_score: float

class CalendarAgent:
    """Base agent class for calendar coordination."""
    
    def __init__(self, email: str, calendar_client: CalendarClient):
        """Initialize the calendar agent.
        
        Args:
            email: Email address of the user this agent represents
            calendar_client: Initialized calendar client
        """
        self.email = email
        self.calendar = calendar_client
        
    def evaluate_meeting_priority(self, event: Dict[str, Any]) -> int:
        """Evaluate the priority of a meeting.
        
        Args:
            event: Calendar event details
            
        Returns:
            Priority score (1-5)
        """
        # If the event already has a priority, use it
        if event.get('priority') is not None:
            return event['priority']
            
        # Default implementation for events without priority
        priority = 3  # Start with medium priority
        
        # More attendees generally means higher priority
        attendees = event.get('attendees', [])
        if len(attendees) > 3:
            priority += 1
        
        # Check if it's a recurring meeting
        if event.get('recurrence'):
            priority -= 1  # Recurring meetings are often more flexible
            
        # Check the title for priority indicators
        title = event.get('summary', '').lower()
        if any(kw in title for kw in ['urgent', 'important', 'priority']):
            priority += 1
        if any(kw in title for kw in ['sync', 'checkin', '1:1']):
            priority -= 1
            
        # Bound priority between 1 and 5
        return max(1, min(5, priority))
    
    def find_meeting_slots(self, request: MeetingRequest, time_min: datetime, time_max: datetime) -> List[MeetingProposal]:
        """Find available meeting slots.
        
        Args:
            request: Meeting request details
            time_min: Start of search range
            time_max: End of search range
            
        Returns:
            List of meeting proposals
        """
        # Get all attendees' events
        all_events = []
        for attendee in [request.organizer] + request.attendees:
            events = self.calendar.get_events(time_min, time_max, owner_email=attendee)
            all_events.extend(events)
        
        # Calculate latest possible start time for this duration
        latest_start_hour = BUSINESS_END_HOUR - (request.duration_minutes // 60)
        latest_start_minute = 60 - (request.duration_minutes % 60) if request.duration_minutes % 60 > 0 else 0
        if latest_start_minute == 60:  # Handle case where duration is exact hours
            latest_start_hour -= 1
            latest_start_minute = 0
        
        logging.info(f"\nEvaluating meeting slots for '{request.title}' (Priority: {request.priority}):")
        logging.info(f"Time range: {time_min.strftime('%Y-%m-%d %I:%M %p')} to {time_max.strftime('%Y-%m-%d %I:%M %p')}")
        logging.info(f"Duration: {request.duration_minutes} minutes")
        logging.info(f"Attendees: {', '.join([request.organizer] + request.attendees)}\n")
        
        # Sort events by start time
        all_events.sort(key=lambda x: x['start']['dateTime'])
        
        # Find available slots
        proposals = []
        current_time = time_min
        
        while current_time < time_max:
            # Skip weekends
            if current_time.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
                # Move to next Monday
                days_to_monday = (7 - current_time.weekday()) % 7
                current_time = (current_time + timedelta(days=days_to_monday)).replace(
                    hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Skip to next business day if outside business hours
            if current_time.hour < BUSINESS_START_HOUR:
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
            elif current_time.hour > latest_start_hour or (current_time.hour == latest_start_hour and current_time.minute > latest_start_minute):
                # Move to next business day
                next_day = current_time + timedelta(days=1)
                # If next day is weekend, skip to Monday
                if next_day.weekday() >= 5:
                    days_to_monday = (7 - next_day.weekday()) % 7
                    current_time = (next_day + timedelta(days=days_to_monday))
                else:
                    current_time = next_day
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Check if this slot works
            proposed_end = current_time + timedelta(minutes=request.duration_minutes)
            conflicts = []
            affected_attendees = set()
            
            for event in all_events:
                # Parse event start and end times and ensure they are timezone-aware
                temp_start = datetime.fromisoformat(event['start']['dateTime'])
                temp_end = datetime.fromisoformat(event['end']['dateTime'])
                
                # Convert to local timezone if needed
                event_start = temp_start.astimezone() if temp_start.tzinfo is not None else temp_start.astimezone()
                event_end = temp_end.astimezone() if temp_end.tzinfo is not None else temp_end.astimezone()
                
                # Check for overlap
                if (event_start < proposed_end and event_end > current_time):
                    event_priority = self.evaluate_meeting_priority(event)
                    
                    # Skip if we can't move this event due to higher priority
                    if event_priority >= request.priority:
                        # This slot won't work due to unmovable conflict
                        conflicts = None
                        break
                        
                    # Add conflict information
                    conflicts.append({
                        'id': event['id'],
                        'title': event['summary'],
                        'start': event_start,
                        'end': event_end,
                        'attendees': [a['email'] for a in event.get('attendees', [])],
                        'priority': event_priority,
                        'new_slot_start': None,  # Will be set if we find an alternative slot
                        'new_slot_end': None
                    })
                    affected_attendees.update(a['email'] for a in event.get('attendees', []))
            
            # Skip this slot if we found an unmovable conflict
            if conflicts is None:
                current_time += timedelta(minutes=30)
                continue
            
            if conflicts:
                # Try to find alternative slots for each conflict
                all_conflicts_resolvable = True
                proposed_end = current_time + timedelta(minutes=request.duration_minutes)
                
                for conflict in conflicts:
                    alternative_slot = self._find_alternative_slot(
                        conflict['start'],
                        conflict['end'],
                        conflict['attendees'],
                        all_events,
                        current_time,  # Pass the proposed meeting start time
                        proposed_end   # Pass the proposed meeting end time
                    )
                    if alternative_slot:
                        conflict['new_slot_start'] = alternative_slot
                        conflict['new_slot_end'] = alternative_slot + (conflict['end'] - conflict['start'])
                        logging.info(f"Found alternative slot for '{conflict['title']}': "
                                   f"{conflict['new_slot_start'].strftime('%I:%M %p')} - "
                                   f"{conflict['new_slot_end'].strftime('%I:%M %p')}")
                    else:
                        all_conflicts_resolvable = False
                        break
                
                if all_conflicts_resolvable:
                    proposals.append(MeetingProposal(
                        request=request,
                        proposed_start_time=current_time,
                        conflicts=conflicts,
                        affected_attendees=list(affected_attendees),
                        impact_score=len(conflicts) + len(affected_attendees) * 0.5
                    ))
            else:
                # Perfect slot found with no conflicts
                proposals.append(MeetingProposal(
                    request=request,
                    proposed_start_time=current_time,
                    conflicts=[],
                    affected_attendees=[],
                    impact_score=0
                ))
            
            current_time += timedelta(minutes=30)
            
            # If next time would be on weekend, skip to Monday
            if (current_time + timedelta(minutes=request.duration_minutes)).weekday() >= 5:
                days_to_monday = (7 - current_time.weekday()) % 7
                current_time = (current_time + timedelta(days=days_to_monday)).replace(
                    hour=BUSINESS_START_HOUR, minute=0)
        
        # Sort proposals by impact score (lower is better)
        proposals.sort(key=lambda p: p.impact_score)
        
        # If we found any perfect matches, return the earliest one
        perfect_matches = [p for p in proposals if not p.conflicts]
        if perfect_matches:
            earliest_perfect_match = min(perfect_matches, key=lambda p: p.proposed_start_time)
            date_str = earliest_perfect_match.proposed_start_time.strftime('%Y-%m-%d')
            slot_time = earliest_perfect_match.proposed_start_time.strftime('%I:%M %p')
            
            logging.info(f"Selected earliest perfect match: {date_str} {slot_time}")
            return [earliest_perfect_match]
        
        return proposals[:3] if proposals else []

    def _prepare_moved_events(self, proposal: MeetingProposal) -> Tuple[bool, Dict[str, Any]]:
        """Prepare events that need to be moved for negotiation.
        
        Args:
            proposal: Meeting proposal with conflicts
            
        Returns:
            Tuple of (success flag, dict of moved events)
        """
        moved_events = {}
        
        for conflict in proposal.conflicts:
            if conflict['priority'] > proposal.request.priority:
                return False, {}
            
            # Format the original time for reference
            original_time = f"{conflict['start'].strftime('%I:%M %p')} - {conflict['end'].strftime('%I:%M %p')}"
            
            # Create the moved event
            moved_events[conflict['id']] = {
                'id': conflict['id'],
                'title': conflict['title'],
                'start_time': conflict['new_slot_start'],
                'end_time': conflict['new_slot_end'],
                'attendees': conflict['attendees'],
                'priority': conflict['priority'],
                'original_time': original_time
            }
            
            logging.info(f"Original time: {conflict['start'].strftime('%Y-%m-%d %I:%M %p')} - {conflict['end'].strftime('%I:%M %p')}")
            logging.info(f"New time: {conflict['new_slot_start'].strftime('%I:%M %p')} - {conflict['new_slot_end'].strftime('%I:%M %p')}")
        
        return True, moved_events

    def _delete_conflict(self, conflict: Dict[str, Any]) -> bool:
        """Delete a conflicting event using its ID.
        
        Args:
            conflict: The conflict event to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        logging.info(f"\nAttempting to delete conflict: {conflict['title']} (ID: {conflict['id']})")
        logging.info(f"Original time: {conflict['start'].strftime('%Y-%m-%d %I:%M %p')} - {conflict['end'].strftime('%I:%M %p')} EST")
        
        if self.calendar.delete_event(conflict['id']):
            logging.info(f"Successfully deleted original event: {conflict['title']} (ID: {conflict['id']})")
            return True
        else:
            logging.error(f"Failed to delete event with ID: {conflict['id']}")
            return False

    def _create_new_meeting(self, proposal: MeetingProposal) -> Dict[str, Any]:
        """Create the new meeting from the proposal.
        
        Args:
            proposal: The meeting proposal
            
        Returns:
            Created event details
        """
        return self.calendar.create_event(
            summary=proposal.request.title,
            start_time=proposal.proposed_start_time,
            end_time=proposal.proposed_start_time + timedelta(minutes=proposal.request.duration_minutes),
            description=proposal.request.description,
            attendees=proposal.request.attendees,
            organizer=proposal.request.organizer,
            priority=proposal.request.priority
        )

    def _create_rescheduled_events(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create the rescheduled events for each conflict.
        
        Args:
            conflicts: List of conflicts to reschedule
            
        Returns:
            List of created events with their IDs
        """
        rescheduled_events = []
        # Use a dictionary to track unique meetings by their original ID
        processed_meetings = {}
        
        for conflict in conflicts:
            # Skip if we've already processed this meeting
            if conflict['id'] in processed_meetings:
                continue
                
            # Mark this meeting as processed
            processed_meetings[conflict['id']] = True
            
            # Get the exact times from the conflict
            start_time = conflict['new_slot_start']
            end_time = conflict['new_slot_end']
            
            # Create the rescheduled event with exact times
            rescheduled = self.calendar.create_event(
                summary=conflict['title'],
                start_time=start_time,
                end_time=end_time,
                description=f"Rescheduled from {conflict['start'].strftime('%I:%M %p')} - {conflict['end'].strftime('%I:%M %p')} EST due to conflict",
                attendees=conflict['attendees'],
                priority=conflict.get('priority', 'N/A')
            )
            if rescheduled:  # Ensure event was created successfully
                logging.info(f"Created rescheduled event: {conflict['title']} (ID: {rescheduled.get('id', 'unknown')}) at {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} EST")
                rescheduled_events.append(rescheduled)
            else:
                logging.error(f"Failed to create rescheduled event: {conflict['title']}")
        return rescheduled_events

    def negotiate_meeting_time(self, proposal: MeetingProposal) -> Dict[str, Any]:
        """Negotiate meeting time by rescheduling conflicts.
        
        Args:
            proposal: Meeting proposal with conflicts
            
        Returns:
            Result of negotiation
        """
        # First try to move all conflicting events
        can_move, moved_events = self._prepare_moved_events(proposal)
        
        if not can_move:
            return {
                "status": "error",
                "message": "Cannot move one or more conflicting events due to priority"
            }
        
        try:
            # First delete all conflicting events
            for event_id in moved_events.keys():
                if not self.calendar.delete_event(event_id):
                    return {
                        "status": "error",
                        "message": f"Failed to delete conflicting event {event_id}"
                    }
            
            # Create the new meeting first to claim the time slot
            proposed_end = proposal.proposed_start_time + timedelta(minutes=proposal.request.duration_minutes)
            
            event = self.calendar.create_event(
                summary=proposal.request.title,
                start_time=proposal.proposed_start_time,
                end_time=proposed_end,
                description=proposal.request.description,
                attendees=proposal.request.attendees,
                organizer=proposal.request.organizer,
                priority=proposal.request.priority
            )
            
            if not event:
                return {
                    "status": "error",
                    "message": "Failed to create new meeting"
                }
            
            # Now recreate all moved events in their new slots
            for event_id, event_data in moved_events.items():
                description = f"Rescheduled from {event_data['original_time']} due to conflict"
                
                # Create the moved event
                moved_event = self.calendar.create_event(
                    summary=event_data['title'],
                    start_time=event_data['start_time'],
                    end_time=event_data['end_time'],
                    description=description,
                    attendees=event_data['attendees'],
                    priority=event_data['priority']
                )
                
                if not moved_event:
                    # If we fail to create a moved event, we should try to clean up
                    self.calendar.delete_event(event['id'])  # Delete the new meeting
                    return {
                        "status": "error",
                        "message": f"Failed to create moved event for {event_data['title']}"
                    }
                
                logging.info(f"Moved event '{event_data['title']}' to "
                            f"{event_data['start_time'].strftime('%I:%M %p')} - "
                            f"{event_data['end_time'].strftime('%I:%M %p')}")
            
            return {
                "status": "success",
                "message": "Successfully scheduled meeting and moved conflicts",
                "event": event,
                "moved_events": moved_events
            }
            
        except Exception as e:
            error_msg = f"Error during negotiation: {str(e)}"
            logging.error(error_msg)
            return {
                "status": "error",
                "message": error_msg
            }

    def _find_alternative_slot(self,
                             original_start: datetime,
                             original_end: datetime,
                             attendees: List[str],
                             existing_events: List[Dict[str, Any]],
                             proposed_meeting_start: Optional[datetime] = None,
                             proposed_meeting_end: Optional[datetime] = None) -> Optional[datetime]:
        """Find an alternative time slot for a meeting that needs to be moved.
        
        Args:
            original_start: Original meeting start time
            original_end: Original meeting end time
            attendees: List of attendee emails
            existing_events: List of all existing events to check against
            proposed_meeting_start: Start time of the proposed new meeting
            proposed_meeting_end: End time of the proposed new meeting
            
        Returns:
            Alternative start time if found, None otherwise
        """
        duration_minutes = int((original_end - original_start).total_seconds() / 60)
        
        # Look for slots in the next 5 business days
        search_start = original_start
        search_end = original_start + timedelta(days=7)  # Extended to 7 days to ensure 5 business days
        
        # Get all busy periods for attendees
        busy_periods = []
        for event in existing_events:
            event_start = datetime.fromisoformat(event['start']['dateTime'])
            event_end = datetime.fromisoformat(event['end']['dateTime'])
            
            # Make times timezone-aware if they aren't already
            if event_start.tzinfo is None:
                event_start = event_start.astimezone()
            if event_end.tzinfo is None:
                event_end = event_end.astimezone()
                
            # Only consider events that affect the attendees of this meeting
            event_attendees = [a['email'] for a in event.get('attendees', [])]
            if any(attendee in event_attendees for attendee in attendees):
                busy_periods.append({
                    'start': event_start,
                    'end': event_end
                })
        
        # Sort busy periods
        busy_periods.sort(key=lambda x: x['start'])
        
        current_time = search_start
        while current_time < search_end:
            # Skip weekends
            if current_time.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
                # Move to next Monday
                days_to_monday = (7 - current_time.weekday()) % 7
                current_time = (current_time + timedelta(days=days_to_monday)).replace(
                    hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Skip to next business day if outside business hours
            if current_time.hour < BUSINESS_START_HOUR:
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
            elif current_time.hour >= BUSINESS_END_HOUR:
                # Move to next business day
                next_day = current_time + timedelta(days=1)
                # If next day is weekend, skip to Monday
                if next_day.weekday() >= 5:
                    days_to_monday = (7 - next_day.weekday()) % 7
                    current_time = (next_day + timedelta(days=days_to_monday))
                else:
                    current_time = next_day
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Calculate potential meeting end time
            potential_end = current_time + timedelta(minutes=duration_minutes)
            
            # Skip if meeting would end after business hours
            if potential_end.hour >= BUSINESS_END_HOUR:
                # Move to next business day
                next_day = current_time + timedelta(days=1)
                # If next day is weekend, skip to Monday
                if next_day.weekday() >= 5:
                    days_to_monday = (7 - next_day.weekday()) % 7
                    current_time = (next_day + timedelta(days=days_to_monday))
                else:
                    current_time = next_day
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Check if this slot works
            has_conflict = False
            
            # First check if this slot overlaps with the proposed meeting time
            if proposed_meeting_start and proposed_meeting_end:
                if (current_time < proposed_meeting_end and potential_end > proposed_meeting_start):
                    has_conflict = True
                    # Move current time to after the proposed meeting
                    current_time = proposed_meeting_end
                    continue
            
            # Then check other conflicts
            for period in busy_periods:
                # Check if this slot overlaps with any busy period
                if (period['start'] <= current_time < period['end'] or
                    period['start'] < potential_end <= period['end'] or
                    (current_time <= period['start'] and potential_end >= period['end'])):
                    has_conflict = True
                    # Move current time to after this conflict
                    current_time = period['end']
                    break
            
            if not has_conflict:
                # Found a slot that doesn't conflict with busy periods or the proposed meeting
                return current_time
            
            # If we had a conflict or the time wasn't suitable, try the next 30-minute slot
            if not has_conflict:
                current_time += timedelta(minutes=30)
        
        return None 