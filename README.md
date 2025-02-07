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

## License

MIT License 