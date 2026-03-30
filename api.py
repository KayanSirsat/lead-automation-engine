import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routes import jobs, leads

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("api").info("LeadFlow API starting up")
    yield
    logging.getLogger("api").info("LeadFlow API shutting down")


app = FastAPI(
    title="LeadFlow API",
    description="Lead generation, enrichment, audit, and outreach pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(leads.router, prefix="/leads", tags=["Leads"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def serve_frontend():
    """Serve the frontend SPA directly from the backend"""
    return FileResponse("index.html")