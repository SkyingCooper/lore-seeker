from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.schema import ForeignKeyConstraint

from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


@event.listens_for(Base.metadata, "before_create")
def _drop_fk_constraints(target, connection, **kw):
    """阻止 create_all 生成 DB 级外键约束，FK 逻辑由应用层保证。"""
    for table in target.tables.values():
        table.constraints = {
            c for c in table.constraints
            if not isinstance(c, ForeignKeyConstraint)
        }


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
