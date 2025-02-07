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
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",  # Allow external access
        port=port,
        workers=1,
        log_level="info"
    )

if __name__ == "__main__":
    main() 
    