from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
client = AsyncIOMotorClient(MONGO_URL)



# Define collections for apartments, users, and temporary users
users = client.get_database("MainDatabase")
users_collections = users.get_collection("AllUsers")
groups = users.get_collection("AllGroups")
tasks = users.get_collection("Tasks")
completedtasks = users.get_collection("CompletedTask")

