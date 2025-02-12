"""
Tests for calendar client functionality.
"""
import pytest
from datetime import datetime, timedelta, timezone
from src.api.calendar_client import CalendarClient

@pytest.fixture
def calendar_client():
    """Create a calendar client for testing."""
    return CalendarClient()

def test_create_event(calendar_client):
    """Test event creation."""
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=1)
    event = calendar_client.create_event(
        summary="Test Event",
        start_time=start_time,
        end_time=end_time,
        description="Test Description",
        attendees=["test@example.com"],
        organizer="organizer@example.com",
        priority=3
    )
    
    assert event is not None
    assert event['summary'] == "Test Event"
    assert event['description'] == "Test Description"
    assert event['priority'] == 3
    assert len(event['attendees']) == 1
    assert event['attendees'][0]['email'] == "test@example.com"
    assert event['organizer']['email'] == "organizer@example.com"

def test_delete_event(calendar_client):
    """Test event deletion."""
    # First create an event
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=1)
    event = calendar_client.create_event(
        summary="Test Event",
        start_time=start_time,
        end_time=end_time,
        attendees=["test@example.com"]
    )
    
    # Then delete it
    assert calendar_client.delete_event(event['id']) is True
    
    # Verify it's deleted
    events = calendar_client.get_events(start_time, end_time, "test@example.com")
    assert len(events) == 0

def test_get_events(calendar_client):
    """Test retrieving events."""
    # Create multiple events
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=1)
    
    # Create events for different users
    calendar_client.create_event(
        summary="Event 1",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        attendees=["user1@example.com"]
    )
    
    calendar_client.create_event(
        summary="Event 2",
        start_time=start_time + timedelta(hours=2),
        end_time=start_time + timedelta(hours=3),
        attendees=["user1@example.com", "user2@example.com"]
    )
    
    # Test getting events for user1
    events = calendar_client.get_events(start_time, end_time, "user1@example.com")
    assert len(events) == 2
    
    # Test getting events for user2
    events = calendar_client.get_events(start_time, end_time, "user2@example.com")
    assert len(events) == 1

def test_find_free_slots(calendar_client):
    """Test finding free time slots."""
    # Create some events
    start_time = datetime.now(timezone.utc).replace(hour=9, minute=0)  # Start at 9 AM
    end_time = start_time + timedelta(days=1)
    
    # Create a busy period
    calendar_client.create_event(
        summary="Busy Period",
        start_time=start_time + timedelta(hours=2),  # 11 AM
        end_time=start_time + timedelta(hours=3),    # 12 PM
        attendees=["test@example.com"]
    )
    
    # Find free slots
    slots = calendar_client.find_free_slots(
        duration_minutes=60,
        start_time=start_time,
        end_time=end_time,
        attendees=["test@example.com"]
    )
    
    assert len(slots) > 0
    # Verify slots don't overlap with busy period
    for slot in slots:
        slot_start = slot['start_time']
        slot_end = slot_start + timedelta(minutes=60)
        assert not (slot_start >= start_time + timedelta(hours=2) and 
                   slot_end <= start_time + timedelta(hours=3))

def test_find_free_slots_with_multiple_attendees(calendar_client):
    """Test finding free slots with multiple attendees."""
    start_time = datetime.now(timezone.utc).replace(hour=9, minute=0)
    end_time = start_time + timedelta(days=1)
    
    # Create overlapping events for different attendees
    calendar_client.create_event(
        summary="Meeting 1",
        start_time=start_time + timedelta(hours=2),
        end_time=start_time + timedelta(hours=3),
        attendees=["user1@example.com"]
    )
    
    calendar_client.create_event(
        summary="Meeting 2",
        start_time=start_time + timedelta(hours=2, minutes=30),
        end_time=start_time + timedelta(hours=3, minutes=30),
        attendees=["user2@example.com"]
    )
    
    # Find free slots
    slots = calendar_client.find_free_slots(
        duration_minutes=60,
        start_time=start_time,
        end_time=end_time,
        attendees=["user1@example.com", "user2@example.com"]
    )
    
    assert len(slots) > 0
    # Verify slots don't overlap with either meeting
    for slot in slots:
        slot_start = slot['start_time']
        slot_end = slot_start + timedelta(minutes=60)
        assert not (slot_start >= start_time + timedelta(hours=2) and 
                   slot_end <= start_time + timedelta(hours=3, minutes=30))

def test_clear_events(calendar_client):
    """Test clearing all events for a user."""
    # Create multiple events
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=1)
    
    calendar_client.create_event(
        summary="Event 1",
        start_time=start_time,
        end_time=end_time,
        attendees=["test@example.com"]
    )
    
    calendar_client.create_event(
        summary="Event 2",
        start_time=start_time + timedelta(hours=2),
        end_time=start_time + timedelta(hours=3),
        attendees=["test@example.com"]
    )
    
    # Clear events
    calendar_client.clear_events("test@example.com")
    
    # Verify events are cleared
    events = calendar_client.get_events(
        start_time,
        start_time + timedelta(days=1),
        "test@example.com"
    )
    assert len(events) == 0

def test_find_free_slots_business_hours(calendar_client):
    """Test that free slots respect business hours."""
    start_time = datetime.now(timezone.utc).replace(hour=0, minute=0)  # Start at midnight
    end_time = start_time + timedelta(days=1)
    
    slots = calendar_client.find_free_slots(
        duration_minutes=60,
        start_time=start_time,
        end_time=end_time,
        attendees=["test@example.com"]
    )
    
    # Verify all slots are within business hours
    for slot in slots:
        slot_time = slot['start_time']
        assert slot_time.hour >= 9  # Business start hour
        assert slot_time.hour < 17  # Business end hour

def test_find_free_slots_duration_validation(calendar_client):
    """Test validation of meeting duration against business hours."""
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=1)
    
    # Try to find slots for a meeting longer than business hours
    slots = calendar_client.find_free_slots(
        duration_minutes=600,  # 10 hours
        start_time=start_time,
        end_time=end_time,
        attendees=["test@example.com"]
    )
    
    assert len(slots) == 1
    assert slots[0]['start_time'] is None
    assert "exceeds total business hours" in slots[0]['rationale'] 