import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Priority order for DB connection:
# 1. If DATABASE_URL is provided, use it directly (must be an async DB URL)
# 2. If MYSQL_* env vars are present, construct a MySQL aiomysql DSN
# 3. Fall back to a local SQLite file using aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    mysql_user = os.getenv("MYSQL_USER")
    mysql_pass = os.getenv("MYSQL_PASSWORD")
    mysql_host = os.getenv("DATABASE_HOST") or os.getenv("MYSQL_HOST")
    mysql_port = os.getenv("DATABASE_PORT") or os.getenv("MYSQL_PORT")
    mysql_db = os.getenv("MYSQL_DATABASE")

    if mysql_user and mysql_pass and mysql_host and mysql_db:
        # async MySQL URL using aiomysql driver
        port_part = f":{mysql_port}" if mysql_port else ""
        DATABASE_URL = f"mysql+aiomysql://{mysql_user}:{mysql_pass}@{mysql_host}{port_part}/{mysql_db}"
    else:
        # Default to local SQLite file (async)
        DATABASE_URL = os.getenv("SQLITE_DATABASE_URL", "sqlite+aiosqlite:///./countries.db")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Create an async session factory
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for all models
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
