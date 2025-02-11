# Calendar Agent

An intelligent calendar management system that uses AI agents to coordinate and optimize meeting schedules across multiple participants.

Test server available at: https://calendar-agent.onrender.com

## Features

- Smart Scheduling: Intelligent rescheduling of lower priority meetings to accommodate important group meetings
- Priority-based Decision Making: Evaluation of meeting priorities for optimal scheduling decisions
- Mock Calendar: Built-in mock calendar for testing and demonstration purposes
- Web Interface: Modern web interface for managing meetings and viewing schedules
- Multiple Scheduling Proposals: System generates multiple alternative proposals with different impact scores
- Force Scheduling Option: Ability to force-schedule meetings without moving conflicts
- User Management: Create and manage calendar users through the interface
- Deduplication: Smart handling of duplicate conflicts and attendees
- Real-time Updates: Calendar view updates automatically when changes are made

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

3. Create a `.env` file with any custom configurations (optional):
```
PORT=8000  # Optional, defaults to 8000
```

## Running Locally

### Development Server

1. Start the server:
```bash
python src/run_server.py
```

The server will start at http://localhost:8000

2. Access the web interface:
- Open your browser and navigate to http://localhost:8000
- Select a test user from the dropdown to view their calendar
- Use the "Schedule Meeting" button to create new meetings
- The system will automatically handle conflicts based on meeting priorities

### Test Data

The system initializes with either:
- Random meetings: 8 meetings per business day for the next month
- Fixed test meetings: A predefined set of meetings for testing (recommended for consistent testing)

To switch between modes, modify the `use_fixed_meetings` parameter in `src/run_server.py`. The default is set to use fixed meetings for more predictable testing.

### Business Hours

The system operates during business hours (9 AM - 5 PM) in your local timezone. Meetings are only scheduled during these hours on business days (Monday-Friday).

## Project Structure

```
calendar_agent/
├── src/
│   ├── api/           # Calendar API and server endpoints
│   ├── agents/        # Agent implementation
│   ├── static/        # Web interface assets (HTML, CSS, JS)
│   ├── utils/         # Utility functions
│   ├── cli.py         # Command-line interface
│   ├── constants.py   # System constants
│   ├── init_test_data.py  # Test data initialization
│   └── run_server.py  # Server startup script
├── tests/             # Test files
├── examples/          # Usage examples
├── docs/             # Documentation
├── requirements.txt  # Project dependencies
├── Procfile         # Render deployment configuration
├── render.yaml      # Render service configuration
└── README.md        # This file
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

## Deployment to Render

1. Fork this repository to your GitHub account

2. Create a new Web Service on Render:
   - Go to https://dashboard.render.com
   - Click "New +" and select "Web Service"
   - Connect your GitHub repository
   - Choose the repository and branch

3. Configure the Web Service:
   - Name: calendar-agent (or your preferred name)
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python src/run_server.py`
   - Select Free plan

4. Click "Create Web Service"

The service will be automatically deployed and available at your Render URL.

## Demo Mode

The system runs in demo mode with pre-configured test users:
- alice@example.com
- bob@example.com
- charlie@example.com
- david@example.com
- eve@example.com

You can use these test accounts to try out the scheduling features.

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
   - Considers business hours (9 AM - 5 PM)
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

## License

MIT License 