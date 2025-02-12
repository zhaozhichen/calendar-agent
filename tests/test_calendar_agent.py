"""
Tests for calendar agent functionality.
"""
import pytest
from datetime import datetime, timedelta, timezone
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
            'start': {'dateTime': '2024-03-20T10:00:00+00:00'},
            'end': {'dateTime': '2024-03-20T11:00:00+00:00'},
            'attendees': [
                {'email': 'alice@example.com'},
                {'email': 'bob@example.com'}
            ],
            'priority': 3
        }
    ]
    
    # Mock create_event
    client.create_event.return_value = {
        'id': '2',
        'summary': 'New Meeting',
        'start': {'dateTime': '2024-03-20T14:00:00+00:00'},
        'end': {'dateTime': '2024-03-20T15:00:00+00:00'},
        'attendees': [
            {'email': 'charlie@example.com'},
            {'email': 'dave@example.com'}
        ]
    }
    
    # Mock delete_event
    client.delete_event.return_value = True
    
    # Mock find_free_slots
    client.find_free_slots.return_value = [
        datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc)
    ]
    
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
    
    # Test meeting with existing priority
    preset_priority = {
        'summary': 'Test Meeting',
        'priority': 4
    }
    assert agent.evaluate_meeting_priority(preset_priority) == 4
    
    # Test meeting with priority keywords
    priority_keywords = {
        'summary': 'Important Urgent Meeting',
        'attendees': [{'email': 'user1@example.com'}]
    }
    assert agent.evaluate_meeting_priority(priority_keywords) > 3

def test_find_meeting_slots(agent, mock_calendar_client):
    """Test finding meeting slots."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3,
        description="Test meeting description"
    )
    
    # Set time range for one week with timezone
    time_min = datetime(2024, 3, 20, 9, 0, tzinfo=timezone.utc)  # 9 AM UTC
    time_max = time_min + timedelta(days=7)
    
    # Mock calendar client response
    mock_calendar_client.get_events.return_value = [
        {
            'id': '1',
            'summary': 'Existing Meeting',
            'start': {'dateTime': '2024-03-20T10:00:00+00:00'},
            'end': {'dateTime': '2024-03-20T11:00:00+00:00'},
            'attendees': [{'email': 'user1@example.com'}]
        }
    ]
    
    proposals = agent.find_meeting_slots(request, time_min, time_max)
    assert len(proposals) > 0
    assert isinstance(proposals[0], MeetingProposal)
    assert proposals[0].request == request

def test_find_meeting_slots_edge_cases(agent, mock_calendar_client):
    """Test edge cases for finding meeting slots."""
    # Test weekend skipping
    request = MeetingRequest(
        title='Weekend Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3
    )
    
    # Start on a Saturday
    time_min = datetime(2024, 3, 23, 9, 0, tzinfo=timezone.utc)  # Saturday
    time_max = time_min + timedelta(days=7)
    
    proposals = agent.find_meeting_slots(request, time_min, time_max)
    assert len(proposals) > 0
    # First proposal should be on Monday
    assert proposals[0].proposed_start_time.weekday() < 5
    
    # Test outside business hours
    time_min = datetime(2024, 3, 20, 6, 0, tzinfo=timezone.utc)  # 6 AM
    time_max = datetime(2024, 3, 20, 20, 0, tzinfo=timezone.utc)  # 8 PM
    
    proposals = agent.find_meeting_slots(request, time_min, time_max)
    assert len(proposals) > 0
    # All proposals should be within business hours
    for proposal in proposals:
        assert proposal.proposed_start_time.hour >= 9  # Business start hour
        assert proposal.proposed_start_time.hour < 17  # Business end hour

def test_find_meeting_slots_with_preferred_times(agent, mock_calendar_client):
    """Test finding meeting slots with preferred time ranges."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3,
        preferred_time_ranges=[
            (
                datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc),
                datetime(2024, 3, 20, 16, 0, tzinfo=timezone.utc)
            )
        ]
    )
    
    time_min = datetime(2024, 3, 20, 9, 0, tzinfo=timezone.utc)
    time_max = time_min + timedelta(days=1)
    
    proposals = agent.find_meeting_slots(request, time_min, time_max)
    assert len(proposals) > 0

def test_find_meeting_slots_no_availability(agent, mock_calendar_client):
    """Test finding meeting slots when no slots are available."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=3
    )
    
    # Mock calendar to return conflicts for all time slots
    mock_calendar_client.get_events.return_value = [
        {
            'id': str(i),
            'summary': f'Meeting {i}',
            'start': {'dateTime': f'2024-03-20T{9+i:02d}:00:00+00:00'},
            'end': {'dateTime': f'2024-03-20T{10+i:02d}:00:00+00:00'},
            'attendees': [{'email': 'user1@example.com'}],
            'priority': 5  # Higher priority than requested meeting
        } for i in range(8)  # Create conflicts for entire business day
    ]
    
    time_min = datetime(2024, 3, 20, 9, 0, tzinfo=timezone.utc)
    time_max = time_min + timedelta(days=1)
    
    proposals = agent.find_meeting_slots(request, time_min, time_max)
    assert len(proposals) == 0

def test_negotiate_meeting_time(agent, mock_calendar_client):
    """Test meeting time negotiation."""
    # Create a proposal with conflicts
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=5,
        description="Test meeting description"
    )
    
    # Create conflict with proper datetime objects
    conflict = {
        'id': '1',
        'summary': 'Existing Meeting',
        'start': datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        'end': datetime(2024, 3, 20, 11, 0, tzinfo=timezone.utc),
        'attendees': [{'email': 'alice@example.com'}, {'email': 'bob@example.com'}],
        'priority': 3,
        'description': 'Existing meeting description',
        'new_slot_start': datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc),
        'new_slot_end': datetime(2024, 3, 20, 15, 0, tzinfo=timezone.utc)
    }
    
    # Calculate impact score based on conflicts and affected attendees
    impact_score = 1 + len(['alice@example.com', 'bob@example.com']) * 0.5
    
    proposal = MeetingProposal(
        request=request,
        proposed_start_time=datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        conflicts=[conflict],
        affected_attendees=['alice@example.com', 'bob@example.com'],
        impact_score=impact_score
    )
    
    result = agent.negotiate_meeting_time(proposal)
    assert result['status'] == 'success'
    assert 'moved_events' in result
    assert len(result['moved_events']) > 0

def test_negotiate_meeting_time_higher_priority_conflict(agent, mock_calendar_client):
    """Test negotiation with higher priority conflict."""
    request = MeetingRequest(
        title='Low Priority Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=2,
        description="Test meeting description"
    )
    
    # Create conflict with higher priority
    conflict = {
        'id': '1',
        'summary': 'High Priority Meeting',
        'start': datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        'end': datetime(2024, 3, 20, 11, 0, tzinfo=timezone.utc),
        'attendees': [{'email': 'alice@example.com'}, {'email': 'bob@example.com'}],
        'priority': 5,  # Higher priority than request
        'description': 'High priority meeting',
        'new_slot_start': datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc),
        'new_slot_end': datetime(2024, 3, 20, 15, 0, tzinfo=timezone.utc)
    }
    
    proposal = MeetingProposal(
        request=request,
        proposed_start_time=datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        conflicts=[conflict],
        affected_attendees=['alice@example.com', 'bob@example.com'],
        impact_score=2.0
    )
    
    result = agent.negotiate_meeting_time(proposal)
    assert result['status'] == 'error'
    assert 'Cannot move one or more conflicting events due to priority' in result['message']

def test_negotiate_meeting_time_with_multiple_conflicts(agent, mock_calendar_client):
    """Test negotiation with multiple conflicts."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=4,
        description="Test meeting description"
    )
    
    # Create multiple conflicts
    conflicts = [
        {
            'id': '1',
            'summary': 'Meeting 1',
            'start': datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
            'end': datetime(2024, 3, 20, 11, 0, tzinfo=timezone.utc),
            'attendees': [{'email': 'alice@example.com'}],
            'priority': 2,
            'description': 'First conflict',
            'new_slot_start': datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc),
            'new_slot_end': datetime(2024, 3, 20, 15, 0, tzinfo=timezone.utc)
        },
        {
            'id': '2',
            'summary': 'Meeting 2',
            'start': datetime(2024, 3, 20, 10, 30, tzinfo=timezone.utc),
            'end': datetime(2024, 3, 20, 11, 30, tzinfo=timezone.utc),
            'attendees': [{'email': 'bob@example.com'}],
            'priority': 3,
            'description': 'Second conflict',
            'new_slot_start': datetime(2024, 3, 20, 15, 0, tzinfo=timezone.utc),
            'new_slot_end': datetime(2024, 3, 20, 16, 0, tzinfo=timezone.utc)
        }
    ]
    
    proposal = MeetingProposal(
        request=request,
        proposed_start_time=datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        conflicts=conflicts,
        affected_attendees=['alice@example.com', 'bob@example.com'],
        impact_score=3.0
    )
    
    result = agent.negotiate_meeting_time(proposal)
    assert result['status'] == 'success'
    assert len(result['moved_events']) == 2

def test_negotiate_meeting_time_create_event_failure(agent, mock_calendar_client):
    """Test negotiation when event creation fails."""
    request = MeetingRequest(
        title='Test Meeting',
        duration_minutes=60,
        organizer='test@example.com',
        attendees=['user1@example.com'],
        priority=4
    )
    
    conflict = {
        'id': '1',
        'summary': 'Existing Meeting',
        'start': datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        'end': datetime(2024, 3, 20, 11, 0, tzinfo=timezone.utc),
        'attendees': [{'email': 'alice@example.com'}],
        'priority': 2,
        'new_slot_start': datetime(2024, 3, 20, 14, 0, tzinfo=timezone.utc),
        'new_slot_end': datetime(2024, 3, 20, 15, 0, tzinfo=timezone.utc)
    }
    
    proposal = MeetingProposal(
        request=request,
        proposed_start_time=datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc),
        conflicts=[conflict],
        affected_attendees=['alice@example.com'],
        impact_score=1.5
    )
    
    # Mock create_event to fail
    mock_calendar_client.create_event.return_value = None
    
    result = agent.negotiate_meeting_time(proposal)
    assert result['status'] == 'error'
    assert 'Failed to create' in result['message']

def test_find_alternative_slot_no_availability(agent, mock_calendar_client):
    """Test finding alternative slot when none are available."""
    original_start = datetime(2024, 3, 20, 10, 0, tzinfo=timezone.utc)
    original_end = datetime(2024, 3, 20, 11, 0, tzinfo=timezone.utc)
    attendees = ['user1@example.com']
    
    # Mock calendar to return conflicts for all time slots
    mock_calendar_client.get_events.return_value = [
        {
            'id': str(i),
            'summary': f'Meeting {i}',
            'start': {'dateTime': f'2024-03-20T{9+i:02d}:00:00+00:00'},
            'end': {'dateTime': f'2024-03-20T{10+i:02d}:00:00+00:00'},
            'attendees': [{'email': 'user1@example.com'}]
        } for i in range(8)  # Create conflicts for entire business day
    ]
    
    alternative_slot = agent._find_alternative_slot(
        original_start,
        original_end,
        attendees,
        mock_calendar_client.get_events.return_value
    )
    
    assert alternative_slot is None 