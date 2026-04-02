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

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# MongoDB connection with Atlas-compatible settings
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME')

if not mongo_url:
    logging.error("MONGO_URL environment variable not set!")
    raise ValueError("MONGO_URL environment variable is required")

if not db_name:
    logging.error("DB_NAME environment variable not set!")
    raise ValueError("DB_NAME environment variable is required")

is_atlas = 'mongodb.net' in mongo_url or 'mongodb+srv' in mongo_url
logging.info(f"MongoDB connection type: {'Atlas' if is_atlas else 'Local'}")
logging.info(f"Database name: {db_name}")

try:
    if is_atlas:
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=120000,
            connectTimeoutMS=60000,
            socketTimeoutMS=120000,
            retryWrites=True,
            retryReads=True,
            maxPoolSize=50,
            minPoolSize=0,
            maxIdleTimeMS=60000,
            waitQueueTimeoutMS=120000,
            appName="BusRoutingApp",
            directConnection=False,
        )
    else:
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=20000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True,
            maxPoolSize=10,
            minPoolSize=1
        )
    db = client[db_name]
    db_connected = False
    logging.info("MongoDB client initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize MongoDB client: {str(e)}")
    client = None
    db = None
    db_connected = False

# Initialize Google Maps client
try:
    google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    if google_maps_key:
        gmaps = googlemaps.Client(key=google_maps_key)
        logging.info("Google Maps client initialized")
    else:
        gmaps = None
        logging.warning("GOOGLE_MAPS_API_KEY not set - geocoding will be disabled")
except Exception as e:
    gmaps = None
    logging.error(f"Failed to initialize Google Maps client: {e}")

# PositionStack API key (free backup geocoding)
POSITIONSTACK_API_KEY = os.environ.get('POSITIONSTACK_API_KEY', '')

# Initialize services
route_optimizer = RouteOptimizer(num_buses=34)
sheets_generator = SheetsDataGenerator()
cover_sheet_generator = CoverSheetGenerator()
route_printer = RoutePrinter(gmaps) if gmaps else None

# CampMinder API setup
_campminder_api_key = os.environ.get('CAMPMINDER_API_KEY', '')
_campminder_subscription_key = os.environ.get('CAMPMINDER_SUBSCRIPTION_KEY', '')
if not _campminder_api_key or not _campminder_subscription_key:
    logging.warning("CampMinder API credentials not configured - parent phone numbers will not be available")
else:
    logging.info("CampMinder API credentials configured")

campminder_api = CampMinderAPI(
    api_key=_campminder_api_key,
    subscription_key=_campminder_subscription_key
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
