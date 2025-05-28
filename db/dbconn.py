from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import motor.motor_asyncio as motor_gridfs  

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

client = AsyncIOMotorClient(MONGO_URL)

db = client.get_database("MainDatabase")

fs = motor_gridfs.AsyncIOMotorGridFSBucket(db)  

users_collections = db.get_collection("AllUsers")

groups = db.get_collection("AllGroups")

tasks = db.get_collection("Tasks")

completedtasks = db.get_collection("CompletedTask")
