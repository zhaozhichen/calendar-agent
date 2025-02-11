"""
Script to run the calendar agent server.
"""
import os
import sys
import logging
import uvicorn
from dotenv import load_dotenv

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.api.calendar_client import CalendarClient
from src.init_test_data import create_test_data

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('calendar_agent.log'),
        logging.StreamHandler()
    ]
)

def main():
    """Run the FastAPI server."""
    # Initialize test data with random meetings
    calendar_client = CalendarClient()
    # create_test_data(calendar_client, use_fixed_meetings=False)
    create_test_data(calendar_client)
    
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(
        "src.api.server:app",  # Updated import path
        host="0.0.0.0",  # Allow external access
        port=port,
        workers=1,
        log_level="info"
    )

if __name__ == "__main__":
    main() 
    