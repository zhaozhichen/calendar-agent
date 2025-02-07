"""
Script to run the calendar agent server.
"""
import uvicorn
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def main():
    """Run the FastAPI server."""
    uvicorn.run(
        "api.server:app",
        host="localhost",
        port=8000,
        reload=True,
        workers=1,
        log_level="debug"
    )

if __name__ == "__main__":
    main() 
    