"""
测试远程 PostgreSQL 和 Redis 连接

用法:
    cd lore-seeker
    source .venv/bin/activate
    python tests/infra/test_connections.py
"""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, "backend")

import asyncpg
import redis.asyncio as aioredis
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _postgres_dsn(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


DB_URL = _postgres_dsn(os.getenv("DATABASE_URL"))
REDIS_URL = os.getenv("REDIS_URL")


def _redis_password(raw_url: str | None) -> str | None:
    if raw_url and urlparse(raw_url).password:
        return None
    return os.getenv("REDIS_PASSWORD")


REDIS_PASSWORD = _redis_password(REDIS_URL)


def require_env() -> None:
    missing = []
    if not DB_URL:
        missing.append("DATABASE_URL")
    if not REDIS_URL:
        missing.append("REDIS_URL")
    if missing:
        print("缺少连接测试环境变量:")
        for name in missing:
            print(f"  - {name}")
        print("\n请在项目根目录 .env 中配置后重试。")
        sys.exit(1)


def describe_target(url: str | None) -> str:
    if not url:
        return "(未配置)"
    parsed = urlparse(url)
    host = parsed.hostname or "(unknown-host)"
    return f"{host}:{parsed.port}" if parsed.port else host


async def test_postgresql():
    print("=" * 50)
    print("[1/2] 测试 PostgreSQL 连接...")
    try:
        conn = await asyncpg.connect(DB_URL, timeout=10)
        version = await conn.fetchval("SELECT version()")
        print(f"  PostgreSQL 连接成功")
        print(f"  版本: {version.split(',')[0]}")

        # 检查 pgvector 扩展
        ext = await conn.fetchrow(
            "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
        )
        if ext:
            print(f"  pgvector 扩展: v{ext['extversion']}")

        # 列出已有表
        tables = await conn.fetch(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
        )
        table_names = [t["tablename"] for t in tables]
        print(f"  已有表 ({len(table_names)}): {', '.join(table_names) if table_names else '(空)'}")

        await conn.close()
        return True
    except Exception as e:
        print(f"  PostgreSQL 连接失败: {e}")
        return False


async def test_redis():
    print("=" * 50)
    print("[2/2] 测试 Redis 连接...")
    try:
        r = aioredis.from_url(REDIS_URL, password=REDIS_PASSWORD or None, socket_connect_timeout=10)
        await r.ping()
        info = await r.info("server")
        print(f"  Redis 连接成功")
        print(f"  版本: {info['redis_version']}")
        mem = info.get("used_memory_human", str(info.get("used_memory", "N/A")))
        print(f"  已用内存: {mem}")

        # 列出已有的 key
        keys = await r.keys("*")
        print(f"  已有 key 数量: {len(keys)}")

        await r.aclose()
        return True
    except Exception as e:
        print(f"  Redis 连接失败: {e}")
        return False


async def main():
    require_env()
    print("\n   Lore Seeker 连接测试")
    print(f"  PostgreSQL 目标: {describe_target(DB_URL)}")
    print(f"  Redis 目标: {describe_target(REDIS_URL)}")
    print()

    db_ok = await test_postgresql()
    redis_ok = await test_redis()

    print("=" * 50)
    if db_ok and redis_ok:
        print("全部连接通过")
    else:
        failed = []
        if not db_ok:
            failed.append("PostgreSQL")
        if not redis_ok:
            failed.append("Redis")
        print(f"连接失败: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
