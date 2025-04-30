import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Data Directories ---
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATABASE_PATH = os.path.join(DATA_DIR, 'copyright_data.db')

# --- Target URLs ---
# List of reliable URLs to scrape for copyright information
# These are placeholder URLs - you'll need to replace them with actual sources
TARGET_URLS = [
    # "https://example.com/public_domain_list", # Uncomment and replace with actual URLs
    # Add more URLs here
]

# --- Scraping Configuration ---
USER_AGENT = "FreeAuthorRightsBot/1.0 (+http://your-project-url.com)"
REQUEST_DELAY_SECONDS = 2  # Time delay between requests to avoid overloading servers

# --- Copyright Configuration ---
# Default copyright term (life of author + 70 years in many jurisdictions)
DEFAULT_TERM_YEARS = 70 

# --- Logging ---
LOG_FILE = os.path.join(BASE_DIR, 'scraper.log')
LOG_LEVEL = logging.INFO  # Can be DEBUG, INFO, WARNING, ERROR

# --- Default Topics ---
# These will be automatically added to the database
PREDEFINED_TOPICS = ["Books", "Movies", "Music"]

# --- AI Configuration ---
# Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
# Batch processing configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))  # Number of works to process in a batch
# Rate limiting for API calls
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "10"))  # Number of calls per minute
