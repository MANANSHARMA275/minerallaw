"""
Tests for Celery timezone configuration (Chunk 4c-prep).

Imports the actual constructed Celery app from celery_worker.py rather than
re-declaring beat_schedule/timezone as a dict — this exercises the real
config_from_object(...) load path. This requires no running worker and no
Redis: Celery(...)'s broker/backend are stored as plain config strings at
construction time; connections are established lazily only when a task is
actually sent/received or a worker/beat process starts its main loop.
celery_worker.py does call create_app() at import time as a side effect,
but tests/conftest.py already forces DATABASE_URL=sqlite:///:memory: before
any test module runs, and nothing here calls db.create_all() or touches the
DB layer at all.
"""
from celery.schedules import crontab

from celery_worker import celery


class TestCeleryTimezoneConfig:

    def test_timezone_is_asia_kolkata(self):
        assert celery.conf.timezone == 'Asia/Kolkata'

    def test_enable_utc_is_explicit_true(self):
        assert celery.conf.enable_utc is True


class TestBeatScheduleEntries:

    def test_all_expected_entries_exist(self):
        expected_keys = {
            'check-sla-timers-every-30-minutes',
            'verify-daily-backup-6am',
            'flag-due-reminders-daily',
        }
        assert set(celery.conf.beat_schedule.keys()) == expected_keys

    def test_verify_daily_backup_fires_at_six_am(self):
        entry = celery.conf.beat_schedule['verify-daily-backup-6am']
        assert entry['schedule'] == crontab(hour=6, minute=0)

    def test_flag_due_reminders_fires_at_seven_am(self):
        entry = celery.conf.beat_schedule['flag-due-reminders-daily']
        assert entry['schedule'] == crontab(hour=7, minute=0)

    def test_sla_timer_runs_every_thirty_minutes(self):
        entry = celery.conf.beat_schedule['check-sla-timers-every-30-minutes']
        assert entry['schedule'] == crontab(minute='*/30')
