from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from app.core.database import SessionLocal
from app.services.queue_service import midnight_reset_all

PKT = pytz.timezone("Asia/Karachi")

scheduler = BackgroundScheduler(timezone=PKT)


def _run_midnight_reset():
    db = SessionLocal()
    try:
        midnight_reset_all(db)
        print("[Scheduler] Midnight reset complete.")
    except Exception as e:
        print(f"[Scheduler] Reset error: {e}")
    finally:
        db.close()


def start_scheduler():
    # Runs at 00:00 PKT every day
    scheduler.add_job(
        _run_midnight_reset,
        CronTrigger(hour=0, minute=0, timezone=PKT),
        id="midnight_reset",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Started — midnight reset job registered (PKT).")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
