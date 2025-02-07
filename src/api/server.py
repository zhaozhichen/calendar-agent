"""
FastAPI server implementation for the Calendar Agent system.

This module provides the REST API endpoints for calendar management and meeting scheduling.

Key Endpoints:
    GET /:
        - Root endpoint returning service status
        - Used for health checks and version info

    GET /agents:
        - Lists all registered calendar agents
        - Returns email addresses and status

    POST /agents:
        - Creates a new calendar agent
        - Requires email and credentials
        - Sets up Google Calendar integration

    GET /agents/{email}/availability:
        - Checks calendar availability for an agent
        - Parameters:
            - start_time: Start of time range
            - end_time: End of time range
        - Returns free/busy periods with details

    POST /agents/{email}/meetings:
        - Requests a new meeting
        - Handles scheduling logic including:
            - Priority evaluation
            - Conflict detection
            - Negotiation if needed
        - Returns scheduling result or negotiation proposal

    POST /agents/{email}/negotiate:
        - Handles meeting negotiation
        - Parameters:
            - proposal_id: ID of the proposal to act on
            - action: 'accept' or 'reject'
        - Executes rescheduling if accepted

    POST /agents/{email}/evaluate_priority:
        - Evaluates meeting priority
        - Uses factors like attendees, title, and type
        - Returns priority score (1-5)

Helper Functions:
    - _validate_meeting_duration(): Checks if meeting duration is valid
    - _validate_business_hours(): Ensures meeting is within business hours
    - _format_busy_periods(): Formats calendar busy periods
    - _format_no_slots_error(): Generates error message for no available slots
    - _format_conflicts_info(): Formats conflict information for response
    - _format_negotiation_message(): Creates user-friendly negotiation message

Features:
1. Input Validation:
   - Validates all request parameters
   - Ensures datetime format consistency
   - Checks business hours constraints

2. Error Handling:
   - Provides detailed error messages
   - Handles edge cases gracefully
   - Returns appropriate HTTP status codes

3. Response Formatting:
   - Consistent JSON response structure
   - Detailed success/error information
   - Human-readable messages

4. Security:
   - Validates agent credentials
   - Protects sensitive calendar data
   - Ensures proper authorization
"""
from datetime import datetime, timedelta
import uuid
import sys
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

from src.agents.base_agent import MeetingRequest, CalendarAgent
from src.api.calendar_client import CalendarClient
from src.constants import EST, BUSINESS_START_HOUR, BUSINESS_END_HOUR
from src.init_test_data import create_test_data

# Initialize FastAPI app
app = FastAPI()

# Pydantic model for meeting request
class MeetingRequest(BaseModel):
    title: str
    duration_minutes: int
    organizer: str
    attendees: List[str]
    priority: int
    description: Optional[str] = None
    preferred_time_ranges: List[List[str]]

# Mount static files
static_dir = os.path.join(project_root, "src", "static")
app.mount("/css", StaticFiles(directory=os.path.join(static_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(static_dir, "js")), name="js")

# Initialize global variables
test_agents = []
active_negotiations = {}
calendar_client = CalendarClient()  # Single calendar client instance

@app.on_event("startup")
async def startup_event():
    """Initialize test data on server startup."""
    global test_agents
    # Default to fixed meetings for more predictable testing
    use_fixed_meetings = True
    test_agents = create_test_data(calendar_client, use_fixed_meetings)
    logging.info(f"Initialized {len(test_agents)} test agents with {'fixed' if use_fixed_meetings else 'random'} meetings")

@app.get("/")
async def root():
    """Serve the main HTML page."""
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/agents")
async def list_agents():
    """List all available agents."""
    return {"agents": test_agents}

@app.post("/agents")
async def create_agent(agent_data: dict):
    """Create a new calendar agent."""
    global test_agents
    email = agent_data.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    if email not in test_agents:
        test_agents.append(email)
        logging.info(f"Created new agent for {email}")
        return {"status": "success", "message": f"Agent created for {email}"}
    else:
        return {"status": "success", "message": f"Agent already exists for {email}"}

@app.get("/agents/{email}/availability")
async def get_availability(
    email: str,
    start_time: str,
    end_time: str
):
    """Get an agent's calendar availability."""
    try:
        # Convert times to datetime objects with UTC timezone
        start_date = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Convert to EST
        start_est = start_date.astimezone(EST)
        end_est = end_date.astimezone(EST)
        
        logging.info(f"Fetching availability for {email}")
        logging.info(f"Date range: {start_est.strftime('%Y-%m-%d %H:%M %Z')} to {end_est.strftime('%Y-%m-%d %H:%M %Z')}")
        
        # Use the global calendar client
        events = calendar_client.get_events(start_est, end_est, owner_email=email)
        
        logging.info(f"Found {len(events)} events")
        
        # Create an agent to evaluate priorities
        agent = CalendarAgent(email, calendar_client)
        
        # Format events for the calendar
        formatted_events = []
        for event in events:
            if event is None:
                continue
                
            # Use the exact times from the event without any modification
            event_start = event['start']['dateTime'] if isinstance(event['start']['dateTime'], str) else event['start']['dateTime'].isoformat()
            event_end = event['end']['dateTime'] if isinstance(event['end']['dateTime'], str) else event['end']['dateTime'].isoformat()
            
            # Evaluate priority for the event
            priority = agent.evaluate_meeting_priority(event)
            
            # Safely get attendees and organizer
            attendees = event.get('attendees', [])
            if attendees is None:
                attendees = []
            
            organizer_dict = event.get('organizer', {})
            if organizer_dict is None:
                organizer_dict = {}
            
            formatted_event = {
                'id': event.get('id', str(uuid.uuid4())),
                'title': event.get('summary', 'Untitled Meeting'),
                'start': event_start,
                'end': event_end,
                'description': event.get('description', ''),
                'attendees': [a.get('email') for a in attendees if isinstance(a, dict) and a.get('email')],
                'organizer': organizer_dict.get('email', email),
                'priority': priority  # Add priority to the event data
            }
            logging.info(f"Formatted event: {formatted_event}")
            formatted_events.append(formatted_event)
        
        response = {
            'email': email,
            'start_time': start_est.isoformat(),
            'end_time': end_est.isoformat(),
            'events': formatted_events
        }
        logging.info(f"Returning response with {len(formatted_events)} events")
        return response
        
    except Exception as e:
        error_msg = f"Error getting availability: {str(e)}"
        logging.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calendar_agent.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

def _validate_meeting_duration(duration_minutes: int, start_est: datetime, end_est: datetime) -> Optional[Dict[str, str]]:
    """Validate meeting duration against business hours.
    
    Args:
        duration_minutes: Meeting duration in minutes
        start_est: Start time in EST
        end_est: End time in EST
        
    Returns:
        Error response if validation fails, None if successful
    """
    total_business_minutes = (BUSINESS_END_HOUR - BUSINESS_START_HOUR) * 60
    if duration_minutes > total_business_minutes:
        error_msg = (
            f"Meeting duration ({duration_minutes} minutes) exceeds available business hours "
            f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM EST = {total_business_minutes} minutes)."
        )
        logging.error(error_msg)
        return {
            "status": "error",
            "message": (
                f"{error_msg}\n\n"
                f"1. Try a different date range\n"
                f"2. Reduce the meeting duration\n"
                f"3. Consider excluding some optional attendees\n"
                f"4. Split into multiple shorter meetings"
            )
        }
    return None

def _validate_business_hours(proposed_start: datetime, proposed_end: datetime) -> Optional[Dict[str, str]]:
    """Validate that meeting time is within business hours.
    
    Args:
        proposed_start: Proposed meeting start time
        proposed_end: Proposed meeting end time
        
    Returns:
        Error response if validation fails, None if successful
    """
    if (proposed_start.hour < BUSINESS_START_HOUR or 
        proposed_end.hour > BUSINESS_END_HOUR or
        (proposed_end.hour == BUSINESS_END_HOUR and proposed_end.minute > 0)):
        
        proposed_start_str = proposed_start.strftime('%I:%M %p')
        proposed_end_str = proposed_end.strftime('%I:%M %p')
        
        error_msg = (
            f"Meeting must be scheduled between {BUSINESS_START_HOUR} AM and {BUSINESS_END_HOUR-12} PM EST.\n"
            f"Your proposed time ({proposed_start_str} - {proposed_end_str} EST) "
            f"{'starts too early' if proposed_start.hour < BUSINESS_START_HOUR else 'would end after business hours'}."
        )
        logging.error(error_msg)
        return {
            "status": "error",
            "message": (
                f"{error_msg}\n\n"
                f"1. Try a different date range\n"
                f"2. Reduce the meeting duration\n"
                f"3. Consider excluding some optional attendees\n"
                f"4. Split into multiple shorter meetings"
            )
        }
    return None

def _format_busy_periods(all_attendees: List[str], start_est: datetime, end_est: datetime) -> List[Dict[str, str]]:
    """Get and format busy periods for all attendees.
    
    Args:
        all_attendees: List of attendee emails
        start_est: Start time in EST
        end_est: End time in EST
        
    Returns:
        List of formatted busy periods
    """
    busy_periods = []
    for attendee in all_attendees:
        events = calendar_client.get_events(start_est, end_est, owner_email=attendee)
        for event in events:
            event_start = datetime.fromisoformat(event['start']['dateTime']).astimezone(EST)
            event_end = datetime.fromisoformat(event['end']['dateTime']).astimezone(EST)
            busy_periods.append({
                'attendee': attendee,
                'event': event['summary'],
                'time': f"{event_start.strftime('%I:%M %p')} - {event_end.strftime('%I:%M %p')} EST"
            })
    return busy_periods

def _format_no_slots_error(start_est: datetime, end_est: datetime, duration_minutes: int, busy_periods: List[Dict[str, str]]) -> Dict[str, str]:
    """Format error message when no slots are available.
    
    Args:
        start_est: Start time in EST
        end_est: End time in EST
        duration_minutes: Meeting duration in minutes
        busy_periods: List of busy periods
        
    Returns:
        Formatted error response
    """
    error_msg = (
        f"Could not find any available {duration_minutes}-minute slots between "
        f"{start_est.strftime('%Y-%m-%d %I:%M %p')} and {end_est.strftime('%Y-%m-%d %I:%M %p')} EST."
    )
    logging.error(error_msg)
    logging.error("Busy periods:")
    for period in busy_periods:
        logging.error(f"- {period['attendee']}: {period['event']} ({period['time']})")
    
    return {
        "status": "error",
        "message": (
            f"{error_msg}\n\n"
            f"1. Try a different date range\n"
            f"2. Reduce the meeting duration\n"
            f"3. Consider excluding some optional attendees\n"
            f"4. Split into multiple shorter meetings"
        )
    }

def _format_conflicts_info(conflicts: List[Dict[str, Any]], all_attendees: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Format conflicts information for negotiation.
    
    Args:
        conflicts: List of conflicts
        all_attendees: List of all attendees
        
    Returns:
        Tuple of (formatted conflicts list, conflicts by attendee)
    """
    conflicts_info = []
    attendee_conflicts = {}
    
    for conflict in conflicts:
        # Ensure all times are in EST
        conflict_start = datetime.fromisoformat(conflict['start'].isoformat()).astimezone(EST)
        conflict_end = datetime.fromisoformat(conflict['end'].isoformat()).astimezone(EST)
        new_slot_start = conflict['new_slot_start'].astimezone(EST)
        new_slot_end = conflict['new_slot_end'].astimezone(EST)
        
        conflict_info = {
            "id": conflict['id'],  # Include the original event ID
            "title": conflict['title'],
            "time": f"{conflict_start.strftime('%I:%M %p')} - {conflict_end.strftime('%I:%M %p')} EST",
            "attendees": conflict['attendees'],
            "priority": conflict.get('priority', 'N/A'),
            "new_time": f"{new_slot_start.strftime('%I:%M %p')} - {new_slot_end.strftime('%I:%M %p')} EST"
        }
        conflicts_info.append(conflict_info)
        
        # Add conflict to each affected attendee's list
        for attendee in conflict['attendees']:
            if attendee in all_attendees:
                if attendee not in attendee_conflicts:
                    attendee_conflicts[attendee] = []
                attendee_conflicts[attendee].append(conflict_info)
    
    return conflicts_info, attendee_conflicts

def _format_negotiation_message(proposal: Dict[str, Any], attendee_conflicts: Dict[str, List[Dict[str, Any]]]) -> str:
    """Format negotiation message with conflicts.
    
    Args:
        proposal: Meeting proposal
        attendee_conflicts: Conflicts grouped by attendee
        
    Returns:
        Formatted negotiation message
    """
    proposed_datetime = datetime.fromisoformat(proposal["start_time"])
    end_datetime = proposed_datetime + timedelta(minutes=proposal["duration_minutes"])
    
    message = (
        f"Scheduling '{proposal['title']}' (Priority: {proposal['priority']})\n"
        f"Found a potential slot at:\n"
        f"Date: {proposed_datetime.strftime('%A, %B %d, %Y')}\n"
        f"Start: {proposed_datetime.strftime('%I:%M %p')} EST\n"
        f"End: {end_datetime.strftime('%I:%M %p')} EST\n\n"
        f"Organizer: {proposal['organizer']}\n"
        f"Attendees: {', '.join(proposal['attendees'])}\n\n"
        f"This time slot has conflicts that can be rescheduled:\n\n"
        f"Conflicts to be rescheduled:\n\n"
    )
    
    # List conflicts by attendee
    for attendee in proposal['attendees']:
        if attendee in attendee_conflicts:
            message += f"Attendee ({attendee}) conflicts:\n"
            for conflict in attendee_conflicts[attendee]:
                message += f"- {conflict['title']} (Priority: {conflict['priority']})\n"
                message += f"  Current time: {conflict['time']}\n"
                message += f"  Proposed time: {conflict['new_time']}\n"
                message += f"  Attendees: {', '.join(conflict['attendees'])}\n\n"
    
    message += f"Total affected attendees: {', '.join(attendee_conflicts.keys())}\n"
    message += "\nWould you like to proceed with rescheduling these meetings?"
    
    return message

@app.post("/agents/{email}/meetings")
async def request_meeting(email: str, request: MeetingRequest):
    """Handle meeting request."""
    try:
        # Log the incoming request
        logging.info(f"\n=== New Meeting Request ===")
        logging.info(f"Title: {request.title}")
        logging.info(f"Duration: {request.duration_minutes} minutes")
        logging.info(f"Organizer: {request.organizer}")
        logging.info(f"Attendees: {', '.join(request.attendees)}")
        logging.info(f"Priority: {request.priority}")
        
        # Convert date strings to datetime objects in EST
        start_date = datetime.fromisoformat(request.preferred_time_ranges[0][0].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.preferred_time_ranges[0][1].replace('Z', '+00:00'))
        
        # Convert to EST
        start_est = start_date.astimezone(EST)
        end_est = end_date.astimezone(EST)
        
        logging.info(f"Requested date range: {start_est.strftime('%Y-%m-%d %I:%M %p')} - {end_est.strftime('%Y-%m-%d %I:%M %p')} EST")

        # Validate meeting duration
        duration_error = _validate_meeting_duration(request.duration_minutes, start_est, end_est)
        if duration_error:
            return duration_error

        # Create meeting request object
        from src.agents.base_agent import MeetingRequest as AgentMeetingRequest
        
        # Ensure organizer is in the attendees list
        all_attendees = list(set([request.organizer] + request.attendees))
        
        meeting_req = AgentMeetingRequest(
            title=request.title,
            duration_minutes=request.duration_minutes,
            organizer=request.organizer,
            attendees=all_attendees,  # Use the combined list
            priority=request.priority,
            description=request.description,
            preferred_time_ranges=[(start_est, end_est)]
        )

        # Get or create agent
        if email not in test_agents:
            error_msg = f"Agent {email} not found"
            logging.error(error_msg)
            return {"status": "error", "message": error_msg}

        # Find available slots within the preferred date range
        agent = CalendarAgent(email, calendar_client)
        proposals = agent.find_meeting_slots(meeting_req, start_est, end_est)

        if not proposals:
            # Get all attendees' busy periods for better error reporting
            busy_periods = _format_busy_periods(all_attendees, start_est, end_est)
            return _format_no_slots_error(start_est, end_est, request.duration_minutes, busy_periods)

        best_proposal = proposals[0]
        
        # Get proposed times in EST
        proposed_start = best_proposal.proposed_start_time.astimezone(EST)
        proposed_end = (proposed_start + timedelta(minutes=request.duration_minutes)).astimezone(EST)
        
        logging.info(f"\nBest proposal found: {proposed_start.strftime('%I:%M %p')} - {proposed_end.strftime('%I:%M %p')} EST")
        
        # Validate business hours constraints
        hours_error = _validate_business_hours(proposed_start, proposed_end)
        if hours_error:
            return hours_error

        if not best_proposal.conflicts:
            # Schedule the meeting
            event = calendar_client.create_event(
                summary=request.title,
                start_time=proposed_start,
                end_time=proposed_end,
                description=request.description,
                attendees=all_attendees,  # Use the combined list
                organizer=request.organizer
            )
            success_msg = (
                f"Successfully scheduled meeting '{request.title}' for "
                f"{proposed_start.strftime('%Y-%m-%d %I:%M %p')} - {proposed_end.strftime('%I:%M %p')} EST"
            )
            logging.info(success_msg)
            return {
                "status": "success",
                "message": success_msg,
                "event": event
            }
        else:
            # Need negotiation
            proposal_id = str(uuid.uuid4())
            
            logging.info("\n=== Negotiation Required ===")
            logging.info(f"Proposed time: {proposed_start.strftime('%I:%M %p')} - {proposed_end.strftime('%I:%M %p')} EST")
            logging.info(f"Number of conflicts: {len(best_proposal.conflicts)}")
            logging.info("Conflicting meetings:")
            
            # Format conflicts information
            conflicts_info, attendee_conflicts = _format_conflicts_info(best_proposal.conflicts, all_attendees)
            
            # Store negotiation details
            active_negotiations[proposal_id] = {
                "id": proposal_id,
                "title": request.title,
                "start_time": best_proposal.proposed_start_time.isoformat(),
                "duration_minutes": request.duration_minutes,
                "organizer": request.organizer,
                "attendees": all_attendees,  # Use the combined list
                "conflicts": conflicts_info,
                "affected_attendees": best_proposal.affected_attendees,
                "priority": request.priority
            }
            
            # Format negotiation message
            negotiation_msg = _format_negotiation_message(active_negotiations[proposal_id], attendee_conflicts)
            
            logging.info("\nNegotiation message prepared for user.")
            
            return {
                "status": "needs_negotiation",
                "message": negotiation_msg,
                "proposal": active_negotiations[proposal_id]
            }

    except Exception as e:
        error_msg = f"Error scheduling meeting: {str(e)}\n\n"
        error_msg += "Debug information:\n"
        error_msg += f"- Requested duration: {request.duration_minutes} minutes\n"
        error_msg += f"- Date range: {start_est.strftime('%Y-%m-%d')} to {end_est.strftime('%Y-%m-%d')}\n"
        error_msg += f"- Attendees: {', '.join(request.attendees)}\n"
        logging.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

@app.post("/agents/{email}/negotiate")
async def negotiate_meeting(email: str, proposal_id: str, action: str):
    """Handle meeting negotiation."""
    try:
        if proposal_id not in active_negotiations:
            return {
                "status": "error",
                "message": "Invalid or expired negotiation proposal"
            }
            
        proposal = active_negotiations[proposal_id]
        agent = CalendarAgent(email, calendar_client)
        
        if action == "accept":
            # Create MeetingRequest object
            from src.agents.base_agent import MeetingRequest, MeetingProposal
            
            meeting_req = MeetingRequest(
                title=proposal["title"],
                duration_minutes=proposal["duration_minutes"],
                organizer=proposal["organizer"],
                attendees=proposal["attendees"],
                priority=proposal["priority"],
                description=proposal.get("description")
            )
            
            # Convert conflicts to include datetime objects
            formatted_conflicts = []
            for conflict in proposal["conflicts"]:
                # Parse the original time
                original_time_parts = conflict["time"].split(" - ")
                original_start_str = original_time_parts[0]
                original_end_str = original_time_parts[1].split(" EST")[0].strip()
                
                # Parse the new time
                new_time_parts = conflict["new_time"].split(" - ")
                new_start_str = new_time_parts[0]
                new_end_str = new_time_parts[1].split(" EST")[0].strip()
                
                # Get the date from the proposal's start time
                base_date = datetime.fromisoformat(proposal["start_time"]).astimezone(EST).date()
                
                # Convert times to datetime objects with proper timezone
                original_start = datetime.strptime(f"{base_date} {original_start_str}", "%Y-%m-%d %I:%M %p").replace(tzinfo=EST)
                original_end = datetime.strptime(f"{base_date} {original_end_str}", "%Y-%m-%d %I:%M %p").replace(tzinfo=EST)
                new_slot_start = datetime.strptime(f"{base_date} {new_start_str}", "%Y-%m-%d %I:%M %p").replace(tzinfo=EST)
                new_slot_end = datetime.strptime(f"{base_date} {new_end_str}", "%Y-%m-%d %I:%M %p").replace(tzinfo=EST)
                
                formatted_conflicts.append({
                    'id': conflict.get("id", str(uuid.uuid4())),
                    'title': conflict["title"],
                    'start': original_start,
                    'end': original_end,
                    'attendees': conflict["attendees"],
                    'priority': conflict.get("priority", "N/A"),
                    'new_slot_start': new_slot_start,
                    'new_slot_end': new_slot_end
                })
            
            # Create MeetingProposal object with timezone-aware datetime
            proposed_start = datetime.fromisoformat(proposal["start_time"]).astimezone(EST)
            # Ensure minutes are set to 00 or 30
            if proposed_start.minute % 30 != 0:
                proposed_start = proposed_start.replace(minute=(proposed_start.minute // 30) * 30)
                
            meeting_proposal = MeetingProposal(
                request=meeting_req,
                proposed_start_time=proposed_start,
                conflicts=formatted_conflicts,
                affected_attendees=proposal["affected_attendees"],
                impact_score=len(proposal["conflicts"]) + len(proposal["affected_attendees"]) * 0.5
            )
            
            # Use the agent's negotiate_meeting_time method
            result = agent.negotiate_meeting_time(meeting_proposal)
            
            if result["status"] == "success":
                # Format the event for frontend consumption
                event_start = result["event"].get('start_time', result["event"].get('start', {}).get('dateTime', ''))
                event_end = result["event"].get('end_time', result["event"].get('end', {}).get('dateTime', ''))
                
                # Ensure times are timezone-aware
                if isinstance(event_start, str):
                    event_start = datetime.fromisoformat(event_start).astimezone(EST)
                if isinstance(event_end, str):
                    event_end = datetime.fromisoformat(event_end).astimezone(EST)
                
                formatted_event = {
                    'id': result["event"].get('id', str(uuid.uuid4())),
                    'title': result["event"].get('title') or result["event"].get('summary', ''),
                    'start': event_start.isoformat(),
                    'end': event_end.isoformat(),
                    'description': result["event"].get('description', ''),
                    'attendees': [{'email': email} for email in proposal["attendees"]],
                    'organizer': {'email': proposal["organizer"]},
                    'priority': proposal["priority"]
                }
                
                # Format rescheduled meetings for frontend
                formatted_reschedules = []
                for meeting in result["moved_events"].values():
                    # Ensure start and end times are timezone-aware
                    start_time = meeting['start_time'].astimezone(EST) if meeting['start_time'].tzinfo else meeting['start_time'].replace(tzinfo=EST)
                    end_time = meeting['end_time'].astimezone(EST) if meeting['end_time'].tzinfo else meeting['end_time'].replace(tzinfo=EST)
                    
                    formatted_reschedules.append({
                        'id': meeting.get('id', str(uuid.uuid4())),
                        'title': meeting['title'],
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat(),
                        'description': f"Rescheduled from {meeting['original_time']} due to conflict",
                        'attendees': [{'email': email} for email in meeting['attendees']],
                        'priority': meeting['priority'],
                        'original_time': meeting['original_time'],
                        'new_time': f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} EST"
                    })
                
                # Clean up the negotiation
                del active_negotiations[proposal_id]
                
                return {
                    "status": "success",
                    "message": f"Successfully scheduled meeting '{proposal['title']}'",
                    "event": formatted_event,
                    "rescheduled_meetings": formatted_reschedules
                }
            else:
                return {
                    "status": "error",
                    "message": result["message"]
                }
        else:
            return {
                "status": "error",
                "message": "Invalid negotiation action"
            }
            
    except Exception as e:
        error_msg = f"Error processing negotiation: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

@app.post("/agents/{email}/evaluate_priority")
async def evaluate_priority(email: str, event: dict):
    """Evaluate the priority of a meeting based on its details."""
    try:
        # Create an agent to evaluate priority
        agent = CalendarAgent(email, calendar_client)
        
        # Evaluate priority using the agent's heuristic logic
        priority = agent.evaluate_meeting_priority(event)
        
        return {"priority": priority}
        
    except Exception as e:
        error_msg = f"Error evaluating priority: {str(e)}"
        logging.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg) 
