"""
Tests for calendar agent functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.agents.base_agent import CalendarAgent, MeetingRequest, MeetingProposal
from src.api.calendar_client import CalendarClient

@pytest.fixture
def mock_calendar_client():
    """Create a mock calendar client."""
    client = Mock(spec=CalendarClient)
    
    # Mock get_events
    client.get_events.return_value = [
        {
            'id': '1',
            'summary': 'Existing Meeting',
            'start': {'dateTime': '2024-03-20T10:00:00Z'},
            'end': {'dateTime': '2024-03-20T11:00:00Z'},
            'attendees': [
                {'email': 'alice@example.com'},
                {'email': 'bob@example.com'}
            ]
        }
    ]
    
    # Mock find_free_slots
    client.find_free_slots.return_value = [
        datetime(2024, 3, 20, 14, 0)  # 2pm UTC
    ]
    
    # Mock create_event
    client.create_event.return_value = {
        'id': '2',
        'summary': 'New Meeting',
        'start': {'dateTime': '2024-03-20T14:00:00Z'},
        'end': {'dateTime': '2024-03-20T15:00:00Z'},
        'attendees': [
            {'email': 'charlie@example.com'},
            {'email': 'dave@example.com'}
        ]
    }
    
    return client

@pytest.fixture
def agent(mock_calendar_client):
    """Create a calendar agent with mock client."""
    return CalendarAgent('test@example.com', mock_calendar_client)

def test_evaluate_meeting_priority(agent):
    """Test meeting priority evaluation."""
    # Test high priority meeting
    high_priority = {
        'summary': 'Urgent Team Meeting',
        'attendees': [{'email': f'user{i}@example.com'} for i in range(6)]
    }
    assert agent.evaluate_meeting_priority(high_priority) > 3
    
    # Test low priority meeting
    low_priority = {
        'summary': '1:1 Sync',
        'attendees': [{'email': 'user1@example.com'}],
        'recurrence': ['FREQ=WEEKLY']
    }
    assert agent.evaluate_meeting_priority(low_priority) < 3

def test_find_meeting_slots(agent, mock_calendar_client):
    """Test finding meeting slots."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3
    )
    
    proposals = agent.find_meeting_slots(request)
    assert len(proposals) > 0
    assert isinstance(proposals[0], MeetingProposal)
    assert proposals[0].proposed_start_time == datetime(2024, 3, 20, 14, 0)

def test_handle_meeting_request_success(agent):
    """Test successful meeting request handling."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3
    )
    
    result = agent.handle_meeting_request(request)
    assert result['status'] == 'success'
    assert 'event' in result
    assert result['event']['summary'] == 'New Meeting'

def test_handle_meeting_request_with_conflicts(agent, mock_calendar_client):
    """Test meeting request handling with conflicts."""
    # Mock no free slots to force conflict
    mock_calendar_client.find_free_slots.return_value = []
    
    request = MeetingRequest(
        title='High Priority Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=5  # High priority to consider moving existing meetings
    )
    
    result = agent.handle_meeting_request(request)
    assert result['status'] == 'needs_negotiation'
    assert 'proposal' in result
    assert 'conflicts' in result['proposal']
    assert len(result['proposal']['conflicts']) > 0

def test_negotiate_meeting_time(agent, mock_calendar_client):
    """Test meeting time negotiation."""
    # Create a proposal with conflicts
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=5
    )
    
    conflicts = mock_calendar_client.get_events()
    proposal = MeetingProposal(
        request=request,
        proposed_start_time=datetime(2024, 3, 20, 10, 0),
        conflicts=conflicts,
        affected_attendees=['alice@example.com', 'bob@example.com']
    )
    
    # Mock successful slot finding for moved meeting
    mock_calendar_client.find_free_slots.return_value = [
        datetime(2024, 3, 20, 14, 0)
    ]
    
    result = agent.negotiate_meeting_time(proposal)
    assert result['status'] == 'success'
    assert 'moved_events' in result
    assert len(result['moved_events']) > 0 