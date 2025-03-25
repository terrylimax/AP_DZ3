from celery.schedules import crontab

beat_schedule = {
    'delete-expired-links-every-minute': {
        'task': 'tasks.tasks.delete_expired_links',
        'schedule': crontab(minute='*'),
    },
}
