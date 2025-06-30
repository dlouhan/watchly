from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_broker_url: str = "redis://redis:6379/0"
    mongo_url: str = "mongodb://mongo:27017"
    mongo_db: str = "scraping_db"
    mongo_snapshot_collection: str = "snapshots"

settings = Settings()