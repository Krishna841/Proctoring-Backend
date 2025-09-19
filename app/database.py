from dotenv import load_dotenv # type: ignore
import os
from motor.motor_asyncio import AsyncIOMotorClient # type: ignore
from pymongo import MongoClient # type: ignore


# Load environment variables from .env file
load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "Proctoring-Backend"

# Async client for FastAPI
client = AsyncIOMotorClient(MONGODB_URL)
database = client[DATABASE_NAME]

# Sync client for operations that need it
sync_client = MongoClient(MONGODB_URL)
sync_database = sync_client[DATABASE_NAME]

# Collections
sessions_collection = database.sessions
events_collection = database.events
