from fastapi import FastAPI
from app.routes import cronjobs, snapshots

app = FastAPI()
app.include_router(cronjobs.router, prefix="/cronjobs", tags=["Cronjobs"])
app.include_router(snapshots.router, prefix="/snapshots", tags=["Snapshots"])