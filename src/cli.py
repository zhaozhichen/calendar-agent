"""
Command-line interface for calendar agents.
"""
import argparse
import json
from datetime import datetime, timedelta
import os
from typing import List, Optional

import aiohttp
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = "http://localhost:8000"

async def create_agent(email: str, credentials_file: str) -> None:
    """Create a new calendar agent.
    
    Args:
        email: Agent's email address
        credentials_file: Path to Google Calendar credentials file
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/agents",
            json={
                "email": email,
                "credentials_file": credentials_file
            }
        ) as response:
            if response.status == 200:
                print(f"Agent created for {email}")
            else:
                print(f"Error creating agent: {await response.text()}")

async def request_meeting(
    organizer_email: str,
    title: str,
    duration_minutes: int,
    attendees: List[str],
    priority: int,
    description: Optional[str] = None
) -> None:
    """Request a new meeting.
    
    Args:
        organizer_email: Email of the organizing agent
        title: Meeting title
        duration_minutes: Meeting duration in minutes
        attendees: List of attendee email addresses
        priority: Meeting priority (1-5)
        description: Optional meeting description
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/agents/{organizer_email}/meetings",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "organizer": organizer_email,
                "attendees": attendees,
                "priority": priority,
                "description": description
            }
        ) as response:
            result = await response.json()
            if response.status == 200:
                if result['status'] == 'success':
                    print("Meeting scheduled successfully!")
                    print(f"Title: {result['event']['summary']}")
                    print(f"Start: {result['event']['start']['dateTime']}")
                    print(f"End: {result['event']['end']['dateTime']}")
                elif result['status'] == 'needs_negotiation':
                    print("Meeting needs negotiation:")
                    print(f"Proposed time: {result['proposal']['start_time']}")
                    print("Conflicts:")
                    for conflict in result['proposal']['conflicts']:
                        print(f"- {conflict['summary']} ({conflict['start']['dateTime']})")
                    print("Affected attendees:", ", ".join(result['proposal']['affected_attendees']))
                else:
                    print(f"Failed to schedule meeting: {result['message']}")
            else:
                print(f"Error requesting meeting: {await response.text()}")

async def check_availability(
    email: str,
    days: int = 7
) -> None:
    """Check an agent's availability.
    
    Args:
        email: Agent's email address
        days: Number of days to check availability for
    """
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(days=days)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/agents/{email}/availability",
            params={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
        ) as response:
            if response.status == 200:
                result = await response.json()
                print(f"\nAvailability for {email}:")
                print(f"Time range: {result['start_time']} to {result['end_time']}")
                print("\nBusy periods:")
                for period in result['busy_periods']:
                    print(f"- {period['title']}")
                    print(f"  From: {period['start']}")
                    print(f"  To: {period['end']}")
            else:
                print(f"Error checking availability: {await response.text()}")

def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Calendar Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create agent command
    create_parser = subparsers.add_parser("create", help="Create a new agent")
    create_parser.add_argument("email", help="Agent's email address")
    create_parser.add_argument("--credentials", help="Path to credentials file",
                             default="credentials.json")
    
    # Request meeting command
    meeting_parser = subparsers.add_parser("meet", help="Request a meeting")
    meeting_parser.add_argument("organizer", help="Organizer's email address")
    meeting_parser.add_argument("title", help="Meeting title")
    meeting_parser.add_argument("--duration", type=int, default=30,
                              help="Meeting duration in minutes")
    meeting_parser.add_argument("--attendees", nargs="+", required=True,
                              help="List of attendee email addresses")
    meeting_parser.add_argument("--priority", type=int, choices=range(1, 6),
                              default=3, help="Meeting priority (1-5)")
    meeting_parser.add_argument("--description", help="Meeting description")
    
    # Check availability command
    avail_parser = subparsers.add_parser("availability",
                                        help="Check agent availability")
    avail_parser.add_argument("email", help="Agent's email address")
    avail_parser.add_argument("--days", type=int, default=7,
                             help="Number of days to check")
    
    args = parser.parse_args()
    
    if args.command == "create":
        asyncio.run(create_agent(args.email, args.credentials))
    elif args.command == "meet":
        asyncio.run(request_meeting(
            args.organizer,
            args.title,
            args.duration,
            args.attendees,
            args.priority,
            args.description
        ))
    elif args.command == "availability":
        asyncio.run(check_availability(args.email, args.days))
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 