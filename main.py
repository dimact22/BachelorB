from fastapi import FastAPI, Request
from db.dbconn import users_collections, create_indexes
from fastapi.middleware.cors import CORSMiddleware
from routes.users import user_app as users  
from telegramfiles.startpage import application
import os
from telegram import Update
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

@app.on_event("startup")
async def init_admin():
    create_indexes()
    admin = await users_collections.find_one({"phone": "+380111111111"})
    if not admin:
        await users_collections.insert_one({
            "phone": "+380111111111",
            "password": "$2b$12$3EbpYte.PmZxSlh113r4g.nHE.KWWh8YFExL2ulKZpNn7iV51CdAK",  
            "status": "admin"
        })
        print("✅ Admin user created")
    else:
        print("ℹ️ Admin user already exists")
    
    await application.initialize()
    await application.bot.set_webhook(
        url=f"{os.getenv('WEBHOOK_URL')}/telegram/webhook"
    )

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

app.include_router(users)
