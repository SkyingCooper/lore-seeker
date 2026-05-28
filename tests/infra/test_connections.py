"""
测试远程 PostgreSQL 和 Redis 连接

用法:
    cd lore-seeker
    source .venv/bin/activate
    python tests/infra/test_connections.py
"""

import asyncio
import sys

sys.path.insert(0, "backend")

import asyncpg
import redis.asyncio as aioredis


DB_URL = "postgresql://loreseeker:loreseeker_pwd@116.62.49.150:5432/loreseeker"
REDIS_URL = "redis://116.62.49.150:6379/0"
REDIS_PASSWORD = "loreseeker_redis"


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
        r = aioredis.from_url(REDIS_URL, password=REDIS_PASSWORD, socket_connect_timeout=10)
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
    print("\n   Lore Seeker 连接测试")
    print(f"  目标: 116.62.49.150")
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
