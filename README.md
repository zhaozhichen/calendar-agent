# Calendar Agent

An intelligent calendar management system that uses AI agents to coordinate and optimize meeting schedules across multiple participants.

## Features

- Calendar Integration: Full access to Google Calendar for viewing, creating, updating, and deleting events
- Agent Communication: Inter-agent protocol for negotiating meeting times
- Smart Scheduling: Intelligent rescheduling of lower priority meetings to accommodate important group meetings
- Priority-based Decision Making: Evaluation of meeting priorities for optimal scheduling decisions

## Setup

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google Calendar API:
- Go to Google Cloud Console
- Create a new project
- Enable the Google Calendar API
- Create OAuth 2.0 credentials
- Download the credentials file as `credentials.json`
- Place it in the project root directory

4. Create a `.env` file with the following variables:
```
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
```

## Project Structure

```
calendar_agent/
├── src/
│   ├── api/           # Calendar API integration
│   ├── agents/        # Agent implementation
│   └── utils/         # Utility functions
├── tests/             # Test files
├── docs/              # Documentation
├── requirements.txt   # Project dependencies
└── README.md         # This file
```

## Development

To run tests:
```bash
pytest tests/
```

To run with coverage:
```bash
pytest --cov=src tests/
```

## Meeting Scheduling System

The Calendar Agent implements an intelligent meeting scheduling system that can handle complex scheduling scenarios through priority-based negotiation and rescheduling. Here's how it works:

### Priority System

Meetings are assigned priority levels from 1 (lowest) to 5 (highest). The priority can be:
- Manually specified when scheduling a meeting
- Automatically calculated based on factors like:
  - Number of attendees (more attendees → higher priority)
  - Meeting title keywords (e.g., "Urgent", "Important" → higher priority)
  - Meeting type (e.g., recurring meetings → lower priority)
  - Attendee roles and organizational hierarchy

### Scheduling Process

1. **Initial Availability Check**
   - System checks all attendees' calendars for the requested time period
   - Considers business hours (9 AM - 5 PM EST by default)
   - Identifies potential time slots that fit the meeting duration

2. **Conflict Resolution**
   - If a free slot is found → Schedule immediately
   - If conflicts exist → Enter negotiation phase

### Negotiation and Rescheduling

When conflicts are detected, the system follows these steps:

1. **Conflict Analysis**
   - Compare priorities of the requested meeting vs. existing meetings
   - Identify all affected attendees
   - Calculate the "impact score" based on:
     - Number of meetings that need to be moved
     - Number of affected attendees
     - Priority differences between meetings

2. **Solution Finding**
   - For each conflicting meeting:
     - Search for alternative time slots
     - Ensure the moved meetings don't create new conflicts
     - Validate that moved meetings stay within business hours
     - Consider the original meeting's priority and attendees

3. **Proposal Generation**
   - Generate a proposal that includes:
     - Suggested time for the new meeting
     - List of meetings that need to be moved
     - New proposed times for moved meetings
     - Complete impact analysis

4. **Approval Process**
   - Present the proposal to the meeting organizer
   - Show all affected meetings and their new times
   - Provide impact analysis and rationale
   - Allow organizer to accept or reject the proposal

5. **Execution**
   - If approved:
     - Delete all affected meetings
     - Create the new high-priority meeting
     - Recreate moved meetings at their new times
     - Notify all affected attendees

### Example Scenario

```
Initial Request:
- New meeting: "Important Team Sync" (Priority 4)
- Duration: 60 minutes
- Attendees: Alice, Bob, Charlie
- Preferred time: Tuesday 2 PM

Conflict Found:
- Existing meeting: "Weekly Update" (Priority 2)
- Current time: Tuesday 2 PM
- Attendees: Bob, Charlie, David

Resolution:
1. System identifies "Weekly Update" can be moved to Tuesday 4 PM
2. Generates proposal showing the move
3. If approved:
   - Moves "Weekly Update" to 4 PM
   - Schedules "Important Team Sync" at 2 PM
   - Notifies all affected attendees
```

### Implementation Details

The negotiation logic is implemented in the `CalendarAgent` class with these key methods:
- `evaluate_meeting_priority()`: Calculates meeting priority
- `find_meeting_slots()`: Finds available slots and identifies conflicts
- `negotiate_meeting_time()`: Handles the negotiation process
- `_prepare_moved_events()`: Prepares the rescheduling plan
- `_create_rescheduled_events()`: Executes the approved changes

## License

MIT License 