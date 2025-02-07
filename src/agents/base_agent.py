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
from src.constants import EST, BUSINESS_START_HOUR, BUSINESS_END_HOUR

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
        """Find possible meeting slots within the given date range."""
        # Convert times to EST if needed
        if time_min.tzinfo != EST:
            time_min = time_min.astimezone(EST)
        if time_max.tzinfo != EST:
            time_max = time_max.astimezone(EST)
        
        # Get events for all attendees within the date range
        all_events = []
        for attendee in [request.organizer] + request.attendees:
            events = self.calendar.get_events(
                owner_email=attendee,
                start_date=time_min,
                end_date=time_max
            )
            all_events.extend(events)
        
        # Try each 30-minute slot during business hours
        business_start = time_min.replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)
        current_time = time_min if time_min > business_start else business_start
        proposals = []
        perfect_matches = []
        
        # Calculate latest possible start time for this duration
        latest_start_hour = BUSINESS_END_HOUR - (request.duration_minutes // 60)
        latest_start_minute = 60 - (request.duration_minutes % 60) if request.duration_minutes % 60 > 0 else 0
        if latest_start_minute == 60:  # Handle case where duration is exact hours
            latest_start_hour -= 1
            latest_start_minute = 0
        
        logging.info(f"\nEvaluating meeting slots for '{request.title}' (Priority: {request.priority}):")
        logging.info(f"Time range: {time_min.strftime('%Y-%m-%d %I:%M %p')} to {time_max.strftime('%Y-%m-%d %I:%M %p')} EST")
        logging.info(f"Duration: {request.duration_minutes} minutes")
        logging.info(f"Attendees: {', '.join([request.organizer] + request.attendees)}\n")
        
        while current_time < time_max:
            # Skip weekends
            if current_time.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                # Move to next Monday
                days_to_monday = (7 - current_time.weekday()) % 7
                current_time = (current_time + timedelta(days=days_to_monday)).replace(
                    hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
                )
                continue
            
            # Skip if not during business hours
            if current_time.hour < BUSINESS_START_HOUR:
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
                
            # Skip if too late to start meeting
            if current_time.hour > latest_start_hour or (current_time.hour == latest_start_hour and current_time.minute > latest_start_minute):
                # Move to next business day
                next_day = current_time + timedelta(days=1)
                # If next day is weekend, move to Monday
                if next_day.weekday() >= 5:
                    days_to_monday = (7 - next_day.weekday()) % 7
                    current_time = (next_day + timedelta(days=days_to_monday))
                else:
                    current_time = next_day
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Calculate meeting end time
            proposed_end = current_time + timedelta(minutes=request.duration_minutes)
            
            # Skip if meeting would end after business hours
            if (proposed_end.hour > BUSINESS_END_HOUR or 
                (proposed_end.hour == BUSINESS_END_HOUR and proposed_end.minute > 0)):
                # Move to next business day
                next_day = current_time + timedelta(days=1)
                # If next day is weekend, move to Monday
                if next_day.weekday() >= 5:
                    days_to_monday = (7 - next_day.weekday()) % 7
                    current_time = (next_day + timedelta(days=days_to_monday))
                else:
                    current_time = next_day
                current_time = current_time.replace(hour=BUSINESS_START_HOUR, minute=0)
                continue
            
            # Find conflicts for this slot
            conflicts = []
            affected_attendees = set()
            has_higher_priority_conflict = False
            all_conflicts_movable = True  # Track if all conflicts can be moved
            
            for event in all_events:
                # Parse event start and end times and ensure they are timezone-aware (assume EST if naive)
                temp_start = datetime.fromisoformat(event['start']['dateTime'])
                temp_end = datetime.fromisoformat(event['end']['dateTime'])
                event_start = temp_start if temp_start.tzinfo is not None else temp_start.replace(tzinfo=EST)
                event_end = temp_end if temp_end.tzinfo is not None else temp_end.replace(tzinfo=EST)

                # Check for overlap using a clear boundary check
                if not (proposed_end <= event_start or current_time >= event_end):
                    event_priority = self.evaluate_meeting_priority(event)
                    event_attendees = [a['email'] for a in event.get('attendees', [])]
                    
                    # Skip this slot if any conflict has higher priority
                    if event_priority > request.priority:
                        has_higher_priority_conflict = True
                        break
                    
                    # Calculate conflict duration
                    conflict_duration = int((event_end - event_start).total_seconds() / 60)
                    
                    # Define the day's business hours for the conflict
                    conflict_day_start = event_start.replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)
                    conflict_day_end = event_start.replace(hour=BUSINESS_END_HOUR, minute=0, second=0, microsecond=0)
                    
                    # Try to find a free slot for this conflict after the proposed meeting
                    potential_slot_start = proposed_end  # This is already at 4:00 PM from the proposal
                    
                    can_move_conflict = False
                    found_slot_start = None
                    found_slot_end = None
                    
                    while potential_slot_start < conflict_day_end:
                        potential_slot_end = potential_slot_start + timedelta(minutes=conflict_duration)
                        
                        # Check if slot is within business hours
                        if (potential_slot_start.hour >= BUSINESS_START_HOUR and 
                            potential_slot_end.hour <= BUSINESS_END_HOUR and
                            (potential_slot_end.hour < BUSINESS_END_HOUR or potential_slot_end.minute == 0)):
                            
                            # Check if this slot works for all attendees
                            slot_has_conflicts = False
                            for attendee in event_attendees:
                                attendee_events = self.calendar.get_events(
                                    start_date=potential_slot_start,
                                    end_date=potential_slot_end,
                                    owner_email=attendee
                                )
                                
                                # Check each event for overlap
                                for other_event in attendee_events:
                                    other_start = datetime.fromisoformat(other_event['start']['dateTime'])
                                    other_end = datetime.fromisoformat(other_event['end']['dateTime'])
                                    
                                    # Skip the original conflict event
                                    if other_event['id'] == event['id']:
                                        continue
                                        
                                    # Check for overlap
                                    if not (potential_slot_end <= other_start or potential_slot_start >= other_end):
                                        slot_has_conflicts = True
                                        break
                                
                                if slot_has_conflicts:
                                    break
                            
                            if not slot_has_conflicts:
                                can_move_conflict = True
                                found_slot_start = potential_slot_start
                                found_slot_end = potential_slot_end
                                break
                        
                        # Try next 30-minute slot
                        potential_slot_start += timedelta(minutes=30)
                    
                    if not can_move_conflict:
                        all_conflicts_movable = False
                        break
                    
                    # Only add the conflict if we found a valid slot for it
                    if can_move_conflict and found_slot_start and found_slot_end:
                        conflicts.append({
                            'id': event['id'],  # Add event ID to conflict info
                            'title': event['summary'],
                            'start': event_start,
                            'end': event_end,
                            'attendees': event_attendees,
                            'priority': event_priority,
                            'new_slot_start': found_slot_start,
                            'new_slot_end': found_slot_end
                        })
                        affected_attendees.update(event_attendees)
                    else:
                        all_conflicts_movable = False
                        break
            
            # Skip this proposal if there's a higher priority conflict or if any conflict can't be moved
            if has_higher_priority_conflict or not all_conflicts_movable:
                current_time += timedelta(minutes=30)
                continue
            
            # Log slot evaluation
            date_str = current_time.strftime('%Y-%m-%d')
            slot_time = current_time.strftime('%I:%M %p')
            
            if len(conflicts) == 0:
                logging.info(f"✓ {date_str} {slot_time}: No conflicts (Perfect match)")
                perfect_matches.append(MeetingProposal(
                    request=request,
                    proposed_start_time=current_time,
                    conflicts=[],
                    affected_attendees=[],
                    impact_score=0
                ))
            else:
                # Only add proposal if all conflicts can be moved
                # Calculate impact score based on number of conflicts and affected attendees
                impact_score = len(conflicts) + len(affected_attendees) * 0.5
                logging.info(f"⚠ {date_str} {slot_time}: {len(conflicts)} conflicts (Impact score: {impact_score:.1f})")
                for conflict in conflicts:
                    logging.info(f"  - '{conflict['title']}' (Priority: {conflict['priority']}) with {', '.join(conflict['attendees'])}")
                    logging.info(f"    Can be moved to: {conflict['new_slot_start'].strftime('%I:%M %p')} - {conflict['new_slot_end'].strftime('%I:%M %p')} EST")
                proposals.append(MeetingProposal(
                    request=request,
                    proposed_start_time=current_time,
                    conflicts=conflicts,
                    affected_attendees=list(affected_attendees),
                    impact_score=impact_score
                ))
            
            # Move to next 30-minute slot
            current_time += timedelta(minutes=30)
        
        # If we found any perfect matches, return the earliest one
        if perfect_matches:
            earliest_perfect_match = min(perfect_matches, key=lambda p: p.proposed_start_time)
            date_str = earliest_perfect_match.proposed_start_time.strftime('%Y-%m-%d')
            slot_time = earliest_perfect_match.proposed_start_time.strftime('%I:%M %p')
            logging.info(f"\nFound {len(perfect_matches)} perfect matches.")
            logging.info(f"Selected earliest perfect match: {date_str} {slot_time}")
            return [earliest_perfect_match]
        
        # Sort proposals by impact score (lower is better)
        sorted_proposals = sorted(proposals, key=lambda p: p.impact_score)
        
        # Log final proposals
        if sorted_proposals:
            logging.info(f"\nFound {len(sorted_proposals)} slots with negotiable conflicts.")
            logging.info("\nTop ranked proposals:")
            # Show top 5 proposals in logs
            for i, proposal in enumerate(sorted_proposals[:5], 1):
                date_str = proposal.proposed_start_time.strftime('%Y-%m-%d')
                slot_time = proposal.proposed_start_time.strftime('%I:%M %p')
                logging.info(f"{i}. {date_str} {slot_time} (Impact score: {proposal.impact_score:.1f}, Conflicts: {len(proposal.conflicts)})")
        else:
            logging.info("\nNo suitable slots found.")
            
        return sorted_proposals

    def _prepare_moved_events(self, proposal: MeetingProposal) -> Tuple[bool, Dict[str, Any]]:
        """Prepare the moved events dictionary from conflicts.
        
        Args:
            proposal: The meeting proposal containing conflicts
            
        Returns:
            Tuple of (success flag, moved events dictionary)
        """
        moved_events = {}
        for conflict in proposal.conflicts:
            # Check priority as a safeguard
            if conflict['priority'] > proposal.request.priority:
                return False, {}

            # Store the original event ID as the key
            original_id = conflict['id']
            moved_events[original_id] = {
                'original_id': original_id,  # Keep track of the original event ID
                'title': conflict['title'],
                'start_time': conflict['new_slot_start'],
                'end_time': conflict['new_slot_end'],
                'attendees': conflict['attendees'],
                'original_time': f"{conflict['start'].strftime('%I:%M %p')} - {conflict['end'].strftime('%I:%M %p')} EST",
                'priority': conflict.get('priority', 'N/A')
            }
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
        """Negotiate meeting time if no free slot is available for all.

        Process:
        - Use the pre-validated slots found during find_meeting_slots
        - Return negotiation details if successful, or a failure message if not.
        """
        # Prepare moved events and check priorities
        negotiation_success, moved_events = self._prepare_moved_events(proposal)
        if not negotiation_success:
            return {'status': 'failure', 'message': 'No available negotiation solution found.'}
        
        # Deduplicate conflicts based on event ID
        unique_conflicts = {}
        for conflict in proposal.conflicts:
            if conflict['id'] not in unique_conflicts:
                unique_conflicts[conflict['id']] = conflict
        
        # Delete all unique conflicting events
        for conflict in unique_conflicts.values():
            if not self._delete_conflict(conflict):
                error_msg = f"Failed to delete original event: {conflict['title']} (ID: {conflict['id']})"
                logging.error(error_msg)
                return {
                    'status': 'failure',
                    'message': error_msg
                }
        
        # Create the new meeting at exactly the proposed time
        proposed_start = proposal.proposed_start_time
        if proposed_start.tzinfo != EST:
            proposed_start = proposed_start.astimezone(EST)
        proposed_end = proposed_start + timedelta(minutes=proposal.request.duration_minutes)
        
        # Create the new meeting
        new_meeting = self.calendar.create_event(
            summary=proposal.request.title,
            start_time=proposed_start,
            end_time=proposed_end,
            description=proposal.request.description,
            attendees=proposal.request.attendees,
            organizer=proposal.request.organizer,
            priority=proposal.request.priority
        )
        if not new_meeting:
            error_msg = "Failed to create new meeting"
            logging.error(error_msg)
            return {
                'status': 'failure',
                'message': error_msg
            }
        
        # Create all rescheduled events and get their new IDs
        rescheduled_events = self._create_rescheduled_events(proposal.conflicts)
        
        # Update moved_events with the new event IDs
        for old_event_id, moved_event in moved_events.items():
            # Find the corresponding rescheduled event
            for rescheduled in rescheduled_events:
                # Safely get the start time from the rescheduled event
                rescheduled_start = None
                if isinstance(rescheduled.get('start'), dict):
                    rescheduled_start = rescheduled['start'].get('dateTime')
                elif isinstance(rescheduled.get('start'), str):
                    rescheduled_start = rescheduled['start']
                
                # Compare title and start time for matching
                if (rescheduled.get('summary') == moved_event['title'] and 
                    rescheduled_start == moved_event['start_time'].isoformat()):
                    moved_event['new_id'] = rescheduled.get('id')
                    break
        
        return {
            'status': 'success',
            'event': new_meeting,
            'moved_events': moved_events
        } 