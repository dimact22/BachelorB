from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import motor.motor_asyncio as motor_gridfs  # Импортируем gridfs через motor

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
client = AsyncIOMotorClient(MONGO_URL)

# Получаем асинхронную базу данных
db = client.get_database("main_collection")

# Используем асинхронный GridFSBucket из motor
fs = motor_gridfs.AsyncIOMotorGridFSBucket(db)  # db теперь асинхронная база данных

# Пример получения коллекций
users_collections = db.get_collection("AllUsers")
groups = db.get_collection("AllGroups")
tasks = db.get_collection("Tasks")
completedtasks = db.get_collection("CompletedTask")
