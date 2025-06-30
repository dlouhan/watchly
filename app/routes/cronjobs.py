from fastapi import APIRouter, HTTPException
from app.models import CronJobCreate
from app.tasks import create_init_snapshot
from pymongo import MongoClient
from app.config import settings
from bson import ObjectId
import datetime

router = APIRouter()
client = MongoClient(settings.mongo_url)
cronjobs_col = client[settings.mongo_db]["cronjobs"]

@router.post("/", summary="Vytvoř nový cronjob a inicializační snapshot")
def create_cronjob(job: CronJobCreate):
    job_id = str(ObjectId())
    cronjob_doc = {
        "_id": job_id,
        "user_id": job.user_id,
        "url": str(job.url),
        "selector": job.selector,
        "check_interval_minutes": job.check_interval_minutes,
        "last_checked": datetime.datetime.utcnow().isoformat(),
        "active": True,
        "notify_on_change": job.notify_on_change,
        "meta": job.meta,
    }
    cronjobs_col.insert_one(cronjob_doc)
    # Vytvoření prvního snapshotu s flagem init
    create_init_snapshot.delay(job_id)
    return {"msg": "Cronjob created", "job_id": job_id}