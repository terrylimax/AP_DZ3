import logging
from celery import Celery
from datetime import datetime
from sqlalchemy import delete
from src.links.models import Link
from src.database import SyncSessionMaker
from fastapi import Depends
import celeryconfig

celery = Celery('tasks', broker='redis://localhost:6379/0')
celery.config_from_object(celeryconfig)

# Указываем, что при старте приложения нужно выполнять повторное подключение к брокеру
celery.conf.broker_connection_retry_on_startup = True

logger = logging.getLogger(__name__)

@celery.task
def delete_expired_links():
    session = SyncSessionMaker()
    try:
        now = datetime.now()
        query = delete(Link).where(Link.expires_at.isnot(None), Link.expires_at < now)
        result = session.execute(query)
        session.commit()
        # Логируем количество удалённых строк (если поддерживается в вашей версии SQLAlchemy)
        deleted_count = result.rowcount if result.rowcount is not None else 0
        logger.info(f"Deleted {deleted_count} expired links at {now.isoformat()}.")
        
    except Exception as e:
        logger.exception("Failed to delete expired links: ")
        session.rollback()
        return {
            "status": 503,
            "details": str(e),
        }
    finally:
        session.close()

    return {
        "status": 204,
        "details": "OK"
    }