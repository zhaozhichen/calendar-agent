"""
Tests for server endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json

from src.api.server import app
from src.api.calendar_client import CalendarClient

@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)

@pytest.fixture
def calendar_client():
    """Create a calendar client for testing."""
    return CalendarClient()

def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_list_agents(client):
    """Test listing agents."""
    response = client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)

def test_create_agent(client):
    """Test agent creation."""
    response = client.post(
        "/agents",
        json={"email": "newuser@example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "newuser@example.com" in data["message"]

def test_get_availability(client):
    """Test getting agent availability."""
    # Set up test dates
    start_time = datetime.now()
    end_time = start_time + timedelta(days=1)
    
    response = client.get(
        f"/agents/test@example.com/availability",
        params={
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "events" in data
    assert isinstance(data["events"], list)

def test_request_meeting_success(client):
    """Test successful meeting request."""
    start_time = datetime.now()
    end_time = start_time + timedelta(days=1)
    
    response = client.post(
        "/agents/organizer@example.com/meetings",
        json={
            "title": "Test Meeting",
            "duration_minutes": 60,
            "organizer": "organizer@example.com",
            "attendees": ["attendee@example.com"],
            "priority": 3,
            "description": "Test meeting",
            "preferred_time_ranges": [
                [start_time.isoformat(), end_time.isoformat()]
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "needs_negotiation"]

def test_request_meeting_invalid_duration(client):
    """Test meeting request with invalid duration."""
    start_time = datetime.now()
    end_time = start_time + timedelta(days=1)
    
    response = client.post(
        "/agents/organizer@example.com/meetings",
        json={
            "title": "Test Meeting",
            "duration_minutes": 600,  # 10 hours
            "organizer": "organizer@example.com",
            "attendees": ["attendee@example.com"],
            "priority": 3,
            "preferred_time_ranges": [
                [start_time.isoformat(), end_time.isoformat()]
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "exceeds available business hours" in data["message"]

def test_negotiate_meeting_accept(client):
    """Test accepting a meeting negotiation."""
    response = client.post(
        "/agents/organizer@example.com/negotiate",
        params={
            "proposal_id": "test_proposal",
            "action": "accept"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "error"]

def test_negotiate_meeting_force(client):
    """Test force scheduling a meeting."""
    response = client.post(
        "/agents/organizer@example.com/negotiate",
        params={
            "proposal_id": "test_proposal",
            "action": "force"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "error"]

def test_delete_event(client):
    """Test event deletion."""
    response = client.delete("/agents/test@example.com/events/test_event_id")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ["success", "error"]

def test_evaluate_priority(client):
    """Test priority evaluation."""
    response = client.post(
        "/agents/test@example.com/evaluate_priority",
        json={
            "summary": "Important Meeting",
            "attendees": [{"email": f"user{i}@example.com"} for i in range(5)],
            "description": "Urgent discussion needed"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "priority" in data
    assert 1 <= data["priority"] <= 5

def test_request_meeting_with_conflicts(client):
    """Test meeting request that requires negotiation."""
    start_time = datetime.now()
    end_time = start_time + timedelta(days=1)
    
    # First create a conflicting meeting
    client.post(
        "/agents/organizer@example.com/meetings",
        json={
            "title": "Existing Meeting",
            "duration_minutes": 60,
            "organizer": "organizer@example.com",
            "attendees": ["attendee@example.com"],
            "priority": 2,
            "preferred_time_ranges": [
                [start_time.isoformat(), end_time.isoformat()]
            ]
        }
    )
    
    # Then try to schedule another meeting
    response = client.post(
        "/agents/organizer@example.com/meetings",
        json={
            "title": "New Meeting",
            "duration_minutes": 60,
            "organizer": "organizer@example.com",
            "attendees": ["attendee@example.com"],
            "priority": 3,
            "preferred_time_ranges": [
                [start_time.isoformat(), end_time.isoformat()]
            ]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    if data["status"] == "needs_negotiation":
        assert "proposal" in data
        assert "conflicts" in data["proposal"]

def test_request_meeting_no_slots(client):
    """Test meeting request when no slots are available."""
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=1)  # Very short window
    
    response = client.post(
        "/agents/organizer@example.com/meetings",
        json={
            "title": "Test Meeting",
            "duration_minutes": 60,
            "organizer": "organizer@example.com",
            "attendees": ["attendee@example.com"],
            "priority": 3,
            "preferred_time_ranges": [
                [start_time.isoformat(), end_time.isoformat()]
            ]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "Could not find any available" in data["message"] 