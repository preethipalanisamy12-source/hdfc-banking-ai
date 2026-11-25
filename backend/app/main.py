from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth
from app.api.routes import profile
from app.api.routes import transactions
from app.api.routes import chat
from app.api.routes import admin


app = FastAPI(title="HDFC Banking AI Assistant")


# Register API routers first
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(transactions.router)
app.include_router(chat.router)
app.include_router(admin.router)


# Mount frontend last
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend"
)