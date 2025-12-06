from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from app.core.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)
async def get_session() -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session
