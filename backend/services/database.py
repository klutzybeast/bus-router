"""Database connection and shared state management."""

import os
import logging
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import googlemaps
from route_optimizer import RouteOptimizer
from sheets_generator import SheetsDataGenerator
from cover_sheet_generator import CoverSheetGenerator
from route_printer import RoutePrinter
from campminder_integration import CampMinderAPI

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.environ['GOOGLE_MAPS_API_KEY'])

# Initialize services
route_optimizer = RouteOptimizer(num_buses=34)
sheets_generator = SheetsDataGenerator()
cover_sheet_generator = CoverSheetGenerator()
route_printer = RoutePrinter(gmaps)
campminder_api = CampMinderAPI(
    api_key=os.environ.get('CAMPMINDER_API_KEY', ''),
    subscription_key=os.environ.get('CAMPMINDER_SUBSCRIPTION_KEY', '')
)

# Configuration
AUTO_SYNC_ENABLED = os.environ.get('AUTO_SYNC_ENABLED', 'true').lower() == 'true'
SYNC_INTERVAL_MINUTES = int(os.environ.get('SYNC_INTERVAL_MINUTES', '15'))
CAMPMINDER_SHEET_ID = os.environ.get('CAMPMINDER_SHEET_ID', '')
OUTPUT_SHEET_ID = os.environ.get('OUTPUT_SHEET_ID', '1ZK58gjF4BO0HF_2y6oovrjzRH3qV5zAs8H-7CeKOSGE')
GOOGLE_SHEETS_WEBHOOK_URL = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '')

# Sync state
sync_task = None
last_sync_time = None


async def shutdown_db():
    """Close database connection."""
    client.close()
