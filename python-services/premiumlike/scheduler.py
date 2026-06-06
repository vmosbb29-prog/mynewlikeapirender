"""
Background scheduler:
 - Every 7 hours: refresh tokens
 - Daily at 03:30 AM UTC: refresh tokens
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

_scheduler = None

def _refresh_job():
    try:
        import app as a
        log.info('Scheduled token refresh triggered.')
        a.do_refresh_tokens(notify_telegram=True)
    except Exception as e:
        log.error(f'_refresh_job error: {e}')

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(timezone='UTC')

    _scheduler.add_job(
        _refresh_job,
        trigger=IntervalTrigger(hours=7),
        id='every_7h',
        name='Refresh every 7 hours',
        replace_existing=True,
    )

    _scheduler.add_job(
        _refresh_job,
        trigger=CronTrigger(hour=3, minute=30, timezone='UTC'),
        id='daily_0330',
        name='Daily 03:30 UTC refresh',
        replace_existing=True,
    )

    _scheduler.start()
    log.info('Scheduler started: every 7h + daily 03:30 UTC')
    return _scheduler

def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
