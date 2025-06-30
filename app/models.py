from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
import datetime

class CronJobCreate(BaseModel):
    user_id: str
    url: HttpUrl
    selector: str
    check_interval_minutes: int = Field(ge=1)
    notify_on_change: bool = True
    meta: Optional[dict] = {}

class SnapshotOut(BaseModel):
    cronjob_id: str
    snapshot_id: int
    scraped_at: str
    html_b64: str
    init: bool
