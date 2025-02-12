"""
Example script demonstrating calendar agent usage.
"""
import asyncio
import os
from datetime import datetime, timedelta

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = "http://localhost:8000"

async def main():
    """Run the example."""
    # Create agents for all participants
    participants = [
        "alice@example.com",
        "bob@example.com",
        "charlie@example.com"
    ]
    
    async with aiohttp.ClientSession() as session:
        # Create agents
        for email in participants:
            print(f"\nCreating agent for {email}...")
            async with session.post(
                f"{BASE_URL}/agents",
                json={
                    "email": email,
                    "credentials_file": "credentials.json"
                }
            ) as response:
                if response.status == 200:
                    print(f"Agent created for {email}")
                else:
                    print(f"Error creating agent: {await response.text()}")
                    return
        
        # Check everyone's availability for the next week
        print("\nChecking availability for all participants...")
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(days=7)
        
        for email in participants:
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
                    print("Busy periods:")
                    for period in result['busy_periods']:
                        print(f"- {period['title']}")
                        print(f"  From: {period['start']}")
                        print(f"  To: {period['end']}")
                else:
                    print(f"Error checking availability: {await response.text()}")
                    return
        
        # Request a high-priority meeting
        print("\nRequesting a high-priority team meeting...")
        async with session.post(
            f"{BASE_URL}/agents/{participants[0]}/meetings",
            json={
                "title": "Important Team Sync",
                "duration_minutes": 60,
                "organizer": participants[0],
                "attendees": participants[1:],
                "priority": 5,
                "description": "Critical team sync meeting to discuss project status"
            }
        ) as response:
            if response.status == 200:
                result = await response.json()
                if result['status'] == 'success':
                    print("\nMeeting scheduled successfully!")
                    print(f"Title: {result['event']['summary']}")
                    print(f"Start: {result['event']['start']['dateTime']}")
                    print(f"End: {result['event']['end']['dateTime']}")
                elif result['status'] == 'needs_negotiation':
                    print("\nMeeting needs negotiation:")
                    print(f"Proposed time: {result['proposal']['start_time']}")
                    print("Conflicts:")
                    for conflict in result['proposal']['conflicts']:
                        print(f"- {conflict['summary']} ({conflict['start']['dateTime']})")
                    print("Affected attendees:", ", ".join(result['proposal']['affected_attendees']))
                    
                    # Accept the negotiation
                    print("\nAccepting negotiation...")
                    async with session.post(
                        f"{BASE_URL}/agents/{participants[0]}/negotiate",
                        params={
                            "proposal_id": result['proposal']['id'],
                            "action": "accept"
                        }
                    ) as neg_response:
                        if neg_response.status == 200:
                            print("Negotiation accepted")
                        else:
                            print(f"Error in negotiation: {await neg_response.text()}")
                else:
                    print(f"Failed to schedule meeting: {result['message']}")
            else:
                print(f"Error requesting meeting: {await response.text()}")

if __name__ == "__main__":
    asyncio.run(main()) 