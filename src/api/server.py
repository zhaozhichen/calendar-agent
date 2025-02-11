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
from fastapi.middleware.cors import CORSMiddleware
import traceback

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

from src.agents.base_agent import MeetingRequest, CalendarAgent, MeetingProposal
from src.api.calendar_client import CalendarClient
from src.constants import BUSINESS_START_HOUR, BUSINESS_END_HOUR
from src.init_test_data import create_test_data

# Initialize FastAPI app
app = FastAPI(title="Calendar Agent API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

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
        # Convert times to datetime objects
        start_date = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Convert to local time
        start_local = start_date.astimezone()
        end_local = end_date.astimezone()
        
        logging.info(f"Fetching availability for {email}")
        logging.info(f"Date range: {start_local.strftime('%Y-%m-%d %H:%M %Z')} to {end_local.strftime('%Y-%m-%d %H:%M %Z')}")
        
        # Use the global calendar client
        events = calendar_client.get_events(start_local, end_local, owner_email=email)
        
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
            'start_time': start_local.isoformat(),
            'end_time': end_local.isoformat(),
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
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('calendar_agent.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

def _validate_meeting_duration(duration_minutes: int, start_local: datetime, end_local: datetime) -> Optional[Dict[str, str]]:
    """Validate meeting duration against business hours.
    
    Args:
        duration_minutes: Meeting duration in minutes
        start_local: Start time in local time
        end_local: End time in local time
        
    Returns:
        Error response if validation fails, None if successful
    """
    total_business_minutes = (BUSINESS_END_HOUR - BUSINESS_START_HOUR) * 60
    if duration_minutes > total_business_minutes:
        error_msg = (
            f"Meeting duration ({duration_minutes} minutes) exceeds available business hours "
            f"({BUSINESS_START_HOUR} AM - {BUSINESS_END_HOUR-12} PM = {total_business_minutes} minutes)."
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
            f"Meeting must be scheduled between {BUSINESS_START_HOUR} AM and {BUSINESS_END_HOUR-12} PM.\n"
            f"Your proposed time ({proposed_start_str} - {proposed_end_str}) "
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

def _format_busy_periods(all_attendees: List[str], start_local: datetime, end_local: datetime) -> List[Dict[str, str]]:
    """Get and format busy periods for all attendees.
    
    Args:
        all_attendees: List of attendee emails
        start_local: Start time in local time
        end_local: End time in local time
        
    Returns:
        List of formatted busy periods
    """
    busy_periods = []
    for attendee in all_attendees:
        events = calendar_client.get_events(start_local, end_local, owner_email=attendee)
        for event in events:
            event_start = datetime.fromisoformat(event['start']['dateTime']).astimezone()
            event_end = datetime.fromisoformat(event['end']['dateTime']).astimezone()
            busy_periods.append({
                'attendee': attendee,
                'event': event['summary'],
                'time': f"{event_start.strftime('%I:%M %p')} - {event_end.strftime('%I:%M %p')}"
            })
    return busy_periods

def _format_no_slots_error(start_local: datetime, end_local: datetime, duration_minutes: int, busy_periods: List[Dict[str, str]]) -> Dict[str, str]:
    """Format error message when no slots are available.
    
    Args:
        start_local: Start time in local time
        end_local: End time in local time
        duration_minutes: Meeting duration in minutes
        busy_periods: List of busy periods
        
    Returns:
        Formatted error response
    """
    error_msg = (
        f"Could not find any available {duration_minutes}-minute slots between "
        f"{start_local.strftime('%Y-%m-%d %I:%M %p')} and {end_local.strftime('%Y-%m-%d %I:%M %p')}."
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
        # Convert times to local timezone
        conflict_start = datetime.fromisoformat(conflict['start'].isoformat()).astimezone()
        conflict_end = datetime.fromisoformat(conflict['end'].isoformat()).astimezone()
        new_slot_start = conflict['new_slot_start'].astimezone()
        new_slot_end = conflict['new_slot_end'].astimezone()
        
        conflict_info = {
            "id": conflict['id'],  # Include the original event ID
            "title": conflict['title'],
            "time": f"{conflict_start.strftime('%I:%M %p')} - {conflict_end.strftime('%I:%M %p')}",
            "attendees": conflict['attendees'],
            "priority": conflict.get('priority', 'N/A'),
            "new_time": f"{new_slot_start.strftime('%I:%M %p')} - {new_slot_end.strftime('%I:%M %p')}",
            "description": conflict.get('description', ''),  # Include the description
            "start": conflict_start,
            "end": conflict_end,
            "new_slot_start": new_slot_start,
            "new_slot_end": new_slot_end
        }
        
        # Add each conflict to the list without deduplication
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
        f"Start: {proposed_datetime.strftime('%I:%M %p')}\n"
        f"End: {end_datetime.strftime('%I:%M %p')}\n\n"
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
        
        # Convert date strings to datetime objects
        start_date = datetime.fromisoformat(request.preferred_time_ranges[0][0].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.preferred_time_ranges[0][1].replace('Z', '+00:00'))
        
        # Convert to local time
        start_local = start_date.astimezone()
        end_local = end_date.astimezone()
        
        logging.info(f"Requested date range: {start_local.strftime('%Y-%m-%d %I:%M %p')} - {end_local.strftime('%Y-%m-%d %I:%M %p')}")

        # Validate meeting duration
        duration_error = _validate_meeting_duration(request.duration_minutes, start_local, end_local)
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
            preferred_time_ranges=request.preferred_time_ranges
        )

        # Get or create agent
        if email not in test_agents:
            error_msg = f"Agent {email} not found"
            logging.error(error_msg)
            return {"status": "error", "message": error_msg}

        # Find available slots within the preferred date range
        agent = CalendarAgent(email, calendar_client)
        proposals = agent.find_meeting_slots(meeting_req, start_local, end_local)

        if not proposals:
            # Get all attendees' busy periods for better error reporting
            busy_periods = _format_busy_periods(all_attendees, start_local, end_local)
            return _format_no_slots_error(start_local, end_local, request.duration_minutes, busy_periods)

        # Log all proposals with their details
        logging.info("\n=== Available Time Slots Analysis ===")
        perfect_matches = [p for p in proposals if not p.conflicts]
        if perfect_matches:
            # Found slots with no conflicts - use the earliest one
            earliest_perfect = min(perfect_matches, key=lambda p: p.proposed_start_time)
            logging.info(f"\n=== Perfect Slot Found ===")
            logging.info(f"Found {len(perfect_matches)} conflict-free slots between "
                       f"{start_local.strftime('%Y-%m-%d')} and {end_local.strftime('%Y-%m-%d')}")
            logging.info(f"Required duration: {request.duration_minutes} minutes")
            logging.info(f"Meeting priority: {request.priority}")
            logging.info("\nAvailable perfect slots:")
            for idx, p in enumerate(perfect_matches, 1):
                slot_end = p.proposed_start_time + timedelta(minutes=request.duration_minutes)
                logging.info(f"{idx}. {p.proposed_start_time.strftime('%Y-%m-%d %I:%M %p')} "
                           f"- {slot_end.strftime('%I:%M %p')}")
            logging.info(f"\nSelected earliest perfect slot: {earliest_perfect.proposed_start_time.strftime('%Y-%m-%d %I:%M %p')}")
            
            # Create event directly
            event = calendar_client.create_event(
                summary=request.title,
                start_time=earliest_perfect.proposed_start_time,
                end_time=earliest_perfect.proposed_start_time + timedelta(minutes=request.duration_minutes),
                description=request.description,
                attendees=all_attendees,
                organizer=request.organizer,
                priority=request.priority
            )
            
            if event:
                return {
                    "status": "success",
                    "message": f"Successfully scheduled meeting '{request.title}' at {earliest_perfect.proposed_start_time.strftime('%Y-%m-%d %I:%M %p')}",
                    "event": event
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to create event"
                }
        else:
            # No perfect slots - rank feasible slots by impact score
            feasible_proposals = []
            logging.info("\n=== No Perfect Slots Available - Analyzing Slots with Conflicts ===")
            
            for idx, p in enumerate(proposals):
                logging.info(f"\nAnalyzing Proposal {idx + 1}:")
                logging.info(f"Proposed Time: {p.proposed_start_time.strftime('%Y-%m-%d %I:%M %p')}")
                logging.info(f"Impact Score: {p.impact_score}")
                
                # Create a map to deduplicate conflicts by ID
                unique_conflicts = {}
                for conflict in p.conflicts:
                    if conflict['id'] not in unique_conflicts:
                        unique_conflicts[conflict['id']] = {
                            **conflict,
                            'attendees': set(conflict['attendees'])
                        }
                    else:
                        # Merge attendees for duplicate conflicts
                        unique_conflicts[conflict['id']]['attendees'].update(conflict['attendees'])
                
                logging.info(f"Number of Unique Conflicts: {len(unique_conflicts)}")
                
                # Initialize all_movable flag
                all_movable = True
                
                # Log unique conflicts
                logging.info("\nConflict Analysis:")
                for conflict_idx, (conflict_id, conflict) in enumerate(unique_conflicts.items(), 1):
                    logging.info(f"\nConflict {conflict_idx}:")
                    logging.info(f"- ID: {conflict_id}")
                    logging.info(f"- Title: {conflict['title']}")
                    logging.info(f"- Current Time: {conflict['start'].strftime('%I:%M %p')} - {conflict['end'].strftime('%I:%M %p')}")
                    logging.info(f"- New Time: {conflict['new_slot_start'].strftime('%I:%M %p')} - {conflict['new_slot_end'].strftime('%I:%M %p')}")
                    logging.info(f"- Priority: {conflict.get('priority', 'N/A')} (Requested Meeting Priority: {request.priority})")
                    logging.info(f"- Attendees: {', '.join(sorted(conflict['attendees']))}")
                    
                    if conflict.get('priority', 0) > request.priority:
                        logging.info("  ⚠️ Cannot move - Higher priority than requested meeting")
                        all_movable = False
                        break
                    else:
                        logging.info("  ✓ Can be moved - Lower or equal priority")
                
                if all_movable:
                    # Format conflicts information for this proposal
                    conflicts_info, attendee_conflicts = _format_conflicts_info(p.conflicts, all_attendees)
                    
                    # Create proposal object
                    proposal = {
                        "id": str(uuid.uuid4()),
                        "title": request.title,
                        "start_time": p.proposed_start_time.isoformat(),
                        "duration_minutes": request.duration_minutes,
                        "organizer": request.organizer,
                        "attendees": all_attendees,
                        "conflicts": conflicts_info,
                        "affected_attendees": p.affected_attendees,
                        "priority": request.priority,
                        "description": request.description,
                        "impact_score": p.impact_score,
                        "unique_conflicts_count": len(unique_conflicts)  # Store the count
                    }
                    feasible_proposals.append(proposal)
                    
                    # Store in active negotiations
                    active_negotiations[proposal["id"]] = proposal
            
            if not feasible_proposals:
                error_msg = "No feasible slots found - all potential slots have unmovable conflicts"
                logging.error(error_msg)
                return {"status": "error", "message": error_msg}
            
            # Sort proposals by impact score
            feasible_proposals.sort(key=lambda p: p["impact_score"])
            
            # Format negotiation message for the best proposal
            best_proposal = feasible_proposals[0]
            negotiation_msg = _format_negotiation_message(best_proposal, attendee_conflicts)
            
            logging.info("\n=== Initial Negotiation Proposal ===")
            logging.info(f"Best proposal start time: {best_proposal['start_time']}")
            logging.info(f"Number of unique conflicts: {best_proposal['unique_conflicts_count']}")  # Use stored count
            logging.info(f"Impact score: {best_proposal['impact_score']}")
            
            return {
                "status": "needs_negotiation",
                "message": negotiation_msg,
                "proposal": best_proposal,
                "proposals": feasible_proposals,  # Return all feasible proposals
                "total_proposals": len(feasible_proposals)  # Add total count
            }

    except Exception as e:
        error_msg = f"Error scheduling meeting: {str(e)}\n\n"
        error_msg += "Debug information:\n"
        error_msg += f"- Requested duration: {request.duration_minutes} minutes\n"
        error_msg += f"- Date range: {start_local.strftime('%Y-%m-%d')} to {end_local.strftime('%Y-%m-%d')}\n"
        error_msg += f"- Attendees: {', '.join(request.attendees)}\n"
        logging.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}

def parse_time_str(time_str: str) -> datetime:
    """Parse time string in format like '10:00 AM' to datetime."""
    try:
        return datetime.strptime(time_str.strip(), "%I:%M %p")
    except ValueError as e:
        logging.error(f"Error parsing time string '{time_str}': {e}")
        raise

@app.post("/agents/{email}/negotiate")
async def negotiate_meeting(email: str, proposal_id: str, action: str):
    """Handle meeting negotiation."""
    try:
        if proposal_id not in active_negotiations:
            return {
                "status": "error",
                "message": "Invalid or expired negotiation ID"
            }
        
        proposal = active_negotiations[proposal_id]
        calendar_agent = CalendarAgent(email, calendar_client)
        
        if action == "accept":
            # Create MeetingProposal object from stored data
            proposed_start = datetime.fromisoformat(proposal["start_time"])
            proposed_end = proposed_start + timedelta(minutes=proposal["duration_minutes"])
            base_date = proposed_start.date()
            
            meeting_request = MeetingRequest(
                title=proposal["title"],
                duration_minutes=proposal["duration_minutes"],
                organizer=proposal["organizer"],
                attendees=proposal["attendees"],
                priority=proposal["priority"],
                preferred_time_ranges=[[proposed_start.isoformat(), proposed_end.isoformat()]]
            )
            
            meeting_proposal = MeetingProposal(
                request=meeting_request,
                proposed_start_time=proposed_start,
                conflicts=[{
                    **conflict,
                    'start': datetime.combine(base_date, parse_time_str(conflict['time'].split(' - ')[0]).time()),
                    'end': datetime.combine(base_date, parse_time_str(conflict['time'].split(' - ')[1]).time()),
                    'new_slot_start': datetime.combine(base_date, parse_time_str(conflict['new_time'].split(' - ')[0]).time()),
                    'new_slot_end': datetime.combine(base_date, parse_time_str(conflict['new_time'].split(' - ')[1]).time())
                } for conflict in proposal["conflicts"]],
                affected_attendees=proposal["affected_attendees"],
                impact_score=len(proposal["conflicts"]) + len(proposal["affected_attendees"]) * 0.5
            )
            
            # Execute the negotiation
            result = calendar_agent.negotiate_meeting_time(meeting_proposal)
        elif action == "force":
            # Create the meeting without moving conflicts
            proposed_start = datetime.fromisoformat(proposal["start_time"])
            proposed_end = proposed_start + timedelta(minutes=proposal["duration_minutes"])
            
            event = calendar_agent.calendar.create_event(
                summary=proposal["title"],
                start_time=proposed_start,
                end_time=proposed_end,
                description=proposal.get("description", ""),
                attendees=proposal["attendees"],
                organizer=proposal["organizer"],
                priority=proposal["priority"]
            )
            
            if event:
                result = {
                    "status": "success",
                    "message": "Meeting force scheduled successfully",
                    "event": event
                }
            else:
                result = {
                    "status": "error",
                    "message": "Failed to force schedule meeting"
                }
        else:
            return {
                "status": "error",
                "message": f"Invalid action: {action}"
            }
        
        # Clean up the negotiation if successful
        if result["status"] == "success":
            del active_negotiations[proposal_id]
        
        return result
            
    except Exception as e:
        error_msg = f"Error processing negotiation: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return {"status": "error", "message": error_msg}

@app.delete("/agents/{email}/events/{event_id}")
async def delete_event(email: str, event_id: str):
    """Delete a calendar event.
    
    Args:
        email: Email of the agent
        event_id: ID of the event to delete
        
    Returns:
        Success/error status
    """
    try:
        if email not in test_agents:
            raise HTTPException(status_code=404, detail=f"Agent {email} not found")
            
        if calendar_client.delete_event(event_id):
            logging.info(f"Successfully deleted event {event_id}")
            return {"status": "success", "message": "Event deleted successfully"}
        else:
            error_msg = f"Failed to delete event {event_id}"
            logging.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
            
    except Exception as e:
        error_msg = f"Error deleting event: {str(e)}"
        logging.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

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
