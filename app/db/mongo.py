"""MongoDB 연결을 여는 유일한 곳. 다른 모듈은 app.db의 컬렉션 핸들을 씁니다."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import DB_NAME, MONGO_URI

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=3000)
db: AsyncIOMotorDatabase = client[DB_NAME]


async def ping() -> None:
    await client.admin.command("ping")


async def close() -> None:
    client.close()
