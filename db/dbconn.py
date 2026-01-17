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

comments = db.get_collection("Comments")

chat_read_state = db.get_collection("ChatReadState")

telegram_users = db.get_collection("TelegramUsers")

def create_indexes():
    comments.create_index("task_id")
    comments.create_index("created_at")
    comments.create_index("author.phone")
    comments.create_index("receiver.phone")

    chat_read_state.create_index(
        [
            ("user_phone", 1),
            ("task_id", 1),
            ("other_user_phone", 1),
        ],
        unique=True
    )


tasks = db.get_collection("Tasks")

completedtasks = db.get_collection("CompletedTask")
