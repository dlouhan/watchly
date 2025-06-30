from fastapi import APIRouter, Query
from app.config import settings
from pymongo import MongoClient

router = APIRouter()
client = MongoClient(settings.mongo_url)
snapshots_col = client[settings.mongo_db]["snapshots"]

@router.get("/{cronjob_id}", summary="Získej všechny snapshoty daného cronjobu")
def get_snapshots(cronjob_id: str):
    snaps = list(
        snapshots_col.find({"cronjob_id": cronjob_id}).sort("snapshot_id", 1)
    )
    for snap in snaps:
        snap["_id"] = str(snap["_id"])
    return snaps