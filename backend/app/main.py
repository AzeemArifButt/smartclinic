from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.routes import auth, queue, tokens, complaints, whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (Alembic handles this in prod)
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="SmartClinic API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(tokens.router, prefix="/api")
app.include_router(complaints.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "SmartClinic API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
