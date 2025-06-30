from app.celery_app import celery_app
from app.config import settings
from pymongo import MongoClient
from playwright.async_api import async_playwright
import datetime
import base64
import asyncio
import logging

mongo_client = MongoClient(settings.mongo_url)
cronjobs_col = mongo_client[settings.mongo_db]["cronjobs"]
snapshots_col = mongo_client[settings.mongo_db]["snapshots"]
checks_col = mongo_client[settings.mongo_db]["checks"]

def round_dt_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def get_last_snapshot_id(cronjob_id):
    last = snapshots_col.find_one(
        {"cronjob_id": cronjob_id},
        sort=[("snapshot_id", -1)]
    )
    logging.info('Last shapshot ID is: %s', last["snapshot_id"])
    return last["snapshot_id"] if last else 1

def get_next_snapshot_id(cronjob_id):
    last = snapshots_col.find_one(
        {"cronjob_id": cronjob_id},
        sort=[("snapshot_id", -1)]
    )

    next = (last["snapshot_id"] + 1) if last else 1
    logging.info('Next shapshot ID is: %s', next)
    return next


def log_check(cronjob_id, selector, old_fragment, new_fragment, change_detected, snapshot_id=None, duration_ms=None):
    check_doc = {
        "cronjob_id": cronjob_id,
        "check_time": datetime.utcnow(),
        "selector": selector,
        "fragment_old": old_fragment,
        "fragment_new": new_fragment,
        "change_detected": change_detected,
        "snapshot_id": snapshot_id,
        "duration_ms": duration_ms,
    }
    checks_col.insert_one(check_doc)

@celery_app.task
def create_init_snapshot(cronjob_id):
    # Najdi cronjob, stáhni stránku, ulož snapshot s init=True
    job = cronjobs_col.find_one({"_id": cronjob_id})
    if not job:
        logging.warning('Cannot find job ID: %s', cronjob_id)
        return
    url = job["url"]
    selector = job["selector"]
    html_b64 = asyncio.run(scrape_and_encode(url))
    logging.info('Scraped html URL: %s', url)
    snapshot_id = 1
    snapshot = {
        "cronjob_id": cronjob_id,
        "snapshot_id": snapshot_id,
        "scraped_at": datetime.utcnow().isoformat(),
        "html_b64": html_b64,
        "init": True,
    }
    logging.info('Creating init snapshot URL: %s for CronJob ID: %s', url, cronjob_id)
    snapshots_col.insert_one(snapshot)
    # Aktualizuj CronJob
    now = round_dt_to_minute(datetime.utcnow())
    logging.info('Update CronJob ID: %s last_checked: %s', cronjob_id, now)
    cronjobs_col.update_one({"_id": cronjob_id}, {"$set": {"last_checked": now}})

    next_check = now + timedelta(minutes=job["check_interval_minutes"])
    cronjobs_col.update_one({"_id": cronjob_id}, {"$set": {"next_check": next_check}})


import base64
from bs4 import BeautifulSoup

def should_store_new_snapshot(cronjob_id, new_html_b64, selector, snapshots_col):
    # Najdi poslední snapshot pro daný cronjob (nejvyšší snapshot_id)
    last = snapshots_col.find_one(
        {"cronjob_id": cronjob_id},
        sort=[("snapshot_id", -1)]
    )

    def extract_fragment(html_b64, selector):
        html = base64.b64decode(html_b64).decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    if not last:
        # První snapshot vždy ulož!
        logging.warning('[SHOULD_STORE_NEW_SNAPSHOT] - did not find any last snapshot(maybe init snapshot??), return true')
        return True
    else:
        last_fragment = extract_fragment(last["html_b64"], selector)
        new_fragment = extract_fragment(new_html_b64, selector)
        logging.info('[SHOULD_STORE_NEW_SNAPSHOT] - last_fragment: %s, new_fragment: %s, return: %s', last_fragment, new_fragment, (last_fragment != new_fragment))
        return last_fragment != new_fragment

@celery_app.task
def create_snapshot(cronjob_id, html_b64):
    # Běžný snapshot (init=False)
    job = cronjobs_col.find_one({"_id": cronjob_id})
    if not job:
        logging.warning('[CREATE_SNAPSHOT] - could not find the cronJob ID: %s', cronjob_id)
        return
    #url = job["url"]
    #selector = job["selector"]
    #html_b64 = asyncio.run(scrape_and_encode(url))

    snapshot_id = get_next_snapshot_id(cronjob_id)
    logging.info('[CREATE_SNAPSHOT] - next shapshot ID: %s', snapshot_id)
    snapshot = {
        "cronjob_id": cronjob_id,
        "snapshot_id": snapshot_id,
        "scraped_at": datetime.utcnow().isoformat(),
        "html_b64": html_b64,
        "init": False,
    }
    logging.info('[CREATE_SNAPSHOT] - inserting shapshot ID: %s', snapshot_id)
    snapshots_col.insert_one(snapshot)

    # Aktualizuj last_checked
    now = round_dt_to_minute(datetime.utcnow())
    next_check = now + timedelta(minutes=job["check_interval_minutes"])
    logging.info('[CREATE_SNAPSHOT] - update cronjob with last_check: %s, next_check:%s', snapshot_id)
    cronjobs_col.update_one({"_id": cronjob_id}, {"$set": {"last_checked": now, "next_check": next_check}})

async def scrape_and_encode(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(str(url), timeout=30000)
        html = await page.content()
        await browser.close()
    return base64.b64encode(html.encode("utf-8")).decode("utf-8")

# PERIODIC SCHEDULER – každý tick zkontroluje cronjoby, kterým vypršel interval
from datetime import datetime, timedelta

@celery_app.task
def scheduler_tick():
    now = round_dt_to_minute(datetime.utcnow())
    jobs = cronjobs_col.find({
        "active": True,
        "next_check": {"$lte": now}
    })

    #Debug
    #job_ids = str(job["_id"] for job in jobs
    logging.info('[SCHEDULER_TICK] - planned jobs: %s', jobs)

    for job in jobs:
        url = job["url"]
        selector = job["selector"]
        html_b64 = asyncio.run(scrape_and_encode(url))
        job_id = str(job["_id"])
        if should_store_new_snapshot(job_id, html_b64, selector, snapshots_col):
            create_snapshot.delay(job_id)
        else:
            pass

from celery.schedules import crontab

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Každou minutu tick
    sender.add_periodic_task(60.0, scheduler_tick.s(), name='tick-cronjob-scheduler')