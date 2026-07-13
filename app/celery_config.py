# ============================================================
# FILE: app/celery_config.py
# PURPOSE: Celery 5.x configuration — task reliability and scheduler
# LAST UPDATED: Phase 1
# NOTE: Uses beat_schedule (Celery 5.x) — NOT deprecated @periodic_task
# ============================================================

from celery.schedules import crontab

# Task reliability — prevents data loss if worker crashes mid-task
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True

# Timezone — crontab entries below are evaluated against this zone, not UTC.
# enable_utc is left at its default (True) explicitly: once `timezone` is
# set, Celery's Celery.timezone property resolves straight to
# timezone.get_timezone(conf.timezone) without consulting enable_utc at all
# (celery/app/base.py) — enable_utc has no effect on crontab-firing time
# here, so there's no correctness reason to change it from the default.
timezone = 'Asia/Kolkata'
enable_utc = True

# Broker — Upstash Redis (same REDIS_URL as Flask-Limiter)
# Set at runtime in celery_worker.py from os.environ

# Celery Beat schedule — Celery 5.x syntax (beat_schedule dict)
beat_schedule = {
    'check-sla-timers-every-30-minutes': {
        'task': 'app.tasks.check_sla_timers',
        'schedule': crontab(minute='*/30'),
    },  # fires: every 30 min (timezone-neutral)
    'verify-daily-backup-6am': {
        'task': 'app.tasks.verify_daily_backup_exists',
        'schedule': crontab(hour=6, minute=0),
    },  # fires: 06:00 IST
    # Runs after the 6 AM backup check, before typical business hours
    'flag-due-reminders-daily': {
        'task': 'app.tasks.flag_due_reminders_task',
        'schedule': crontab(hour=7, minute=0),
    },  # fires: 07:00 IST
}
