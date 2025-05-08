from fastapi import FastAPI
from db.dbconn import users_collections
from fastapi.middleware.cors import CORSMiddleware
from routes.users import user_app as users  # Import the correct router object

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware to handle cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

@app.on_event("startup")
async def init_admin():
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

# Include the `users` router
app.include_router(users)
