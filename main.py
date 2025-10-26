from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware import add_request_id_and_process_time
from database import engine,Base
from logger import get_logger
from routers import router

logger = get_logger(__name__)   

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Application shutdown complete.")
app = FastAPI(lifespan=lifespan, title="Country Data, Country Currency & Exchange API", version="1.0.0")

app.middleware('http')(add_request_id_and_process_time)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    logger.info("Root endpoint called")
    return {"message" :"Welcome to FastAPI App for Country Data, Country Currency & Exchange API"}

app.include_router(router, tags=["Countries"])