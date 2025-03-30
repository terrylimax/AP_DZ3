from math import e
from os import replace
from urllib import response
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from src.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse
from typing import Optional, List
from sqlalchemy import select, insert, delete, update
from datetime import datetime
from .schemas import LinkCreate, LinkResponse
from .models import Link
import random
import string
from celery import Celery
from redis.asyncio import Redis
import json 
from auth.db import User
from auth.users import current_active_user, get_optional_current_user

app = FastAPI()

# Создаём роутер с префиксом
router = APIRouter(
    prefix="/links",
    tags=["Links"]
)

redis_client = Redis(host='localhost', port=6379, db=1)

# Генерация сокращённой ссылки
def generate_short_url():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

@router.post("/shorten")
async def shorten_url(
    original_link: str, 
    session: AsyncSession = Depends(get_async_session),
    custom_alias: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    user: Optional[User] = Depends(get_optional_current_user)  # опционально получаем авторизованного пользователя
):
    try:
        #проверяем, есть ли оригинальная ссылка в базе данных
        query = select(Link).where(Link.original_link == original_link)
        result = await session.execute(query)
        original_url_existing = result.scalar_one_or_none()
        
        if original_url_existing:
            # Если оригинальная ссылка уже есть в базе данных, возвращаем существующую укороченную ссылку
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "error",
                    "error": {
                        "message": "Short code already exists",
                        "short_code": original_url_existing.shortened_link
                    }
                }
            )
            
        if custom_alias:
            short_url = custom_alias
        else:
            # Проверяем, содержится сгенерированная укороченная ссылка в таблице links
            short_url = generate_short_url()
        query = select(Link).where(Link.shortened_link == short_url)
        result = await session.execute(query)
        
        existing = result.scalar_one_or_none()
        while existing:
            if custom_alias:
                raise HTTPException(status_code=409, detail="Custom alias provided already exists")
            short_url = generate_short_url()
            query = select(Link).where(Link.shortened_link == short_url)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()

        
        
        # пока только 1 версия схемы данных для добавления для гостей 
        new_link = LinkCreate(
            user_id=user.id if user else None,
            original_link=original_link, 
            shortened_link=short_url,
            custom_alias=True if custom_alias else False,
            expires_at=expires_at.replace(second=0,microsecond=0) if expires_at else None
        )
        
        # Добавляем новую ссылку в базу данных
        new_link_dict = new_link.model_dump()
        statement = insert(Link).values(**new_link_dict)
        await session.execute(statement)
        await session.commit()
        
        return {"status": "success", "short_url": short_url}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error": str(e)
        })

@router.get("/search", response_model=List[LinkResponse])
async def search_links(
    original_url: str = Query(..., description="Оригинальный URL для поиска"),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        '''Поиск укороченных ссылок по оригинальному URL'''
        query = select(Link).where(Link.original_link == original_url)
        result = await session.execute(query)
        links = result.scalars().all()
        
        if not links:
            raise HTTPException(status_code=404, detail="No records found with the provided original URL") 
        
        link_responses = [
            LinkResponse(
                original_link=link.original_link,
                shortened_link=link.shortened_link,
                last_used=link.last_used,
                custom_alias=link.custom_alias
            )
            for link in links
        ]
        
        return link_responses
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
async def get_link_by_short_code(short_code: str, session: AsyncSession = Depends(get_async_session)) -> Link:
    try:
        '''Получение объекта ссылки по укороченному коду'''
        query = select(Link).where(Link.shortened_link == short_code)
        result = await session.execute(query)
        original_link_object = result.scalar_one_or_none()
        
        if original_link_object is None:
            raise HTTPException(status_code=404, detail="Short code not found")
        
        return original_link_object
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error": str(e)
        })

@router.get("/{short_code}")
async def redirect_to_original(
    short_code: str, 
    session: AsyncSession = Depends(get_async_session)
):
    '''Перенаправление на оригинальную ссылку'''
    try:
        # Получаем объект ссылки для обновления счётчика
        original_link_object = await get_link_by_short_code(short_code, session)
        
        # Увеличиваем счётчик использования и обновляем время последнего использования
        original_link_object.used_count += 1 #type: ignore
        original_link_object.last_used = datetime.now() #type: ignore
        await session.commit()
        
        # Сначала пытаемся получить кэшированные данные из Redis
        cached_data = await redis_client.get(f"cached_link:{short_code}")
        if cached_data:
            data = json.loads(cached_data)
            """#Выводим оригинальный URL из кэша для Swagger UI
            return {
                "status": "success",
                "original_link": data["original_link"],
                "cached": True
            }"""
            #делаем редирект по оригинальному URL из кэша (работает в клиенте браузера)
            return RedirectResponse(url=data["original_link"])
        
        # Если кэш не найден – редирект по оригинальному URL из базы
        original_url = original_link_object.original_link
        
        # если used_count равен 5, сохранить данные в кэш Redis
        if original_link_object.used_count == 5: #type: ignore
            data = {
                "original_link": original_link_object.original_link,
                "shortened_link": original_link_object.shortened_link,
                "cached_at": datetime.now().isoformat()
            }
            redis_client.set(f"cached_link:{short_code}", json.dumps(data))
        
        return RedirectResponse(url=original_url) #type: ignore
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error": str(e)
        })

@router.delete("/{short_code}")
async def delete_short_code(
    short_code: str,
    user: User = Depends(current_active_user),  # только зарегистрированные пользователи могут удалять ссылки
    original_link_object = Depends(get_link_by_short_code), 
    session: AsyncSession = Depends(get_async_session)
):
    try:
        # Удаляем запись по полю shortened_link, полученному из зависимости
        query = delete(Link).where(Link.shortened_link == original_link_object.shortened_link)
        await session.execute(query)
        await session.commit()
        
        # Чистим кэш для данного short_code
        await redis_client.delete(f"cached_link:{short_code}")
        
        return {"status": "success"}
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error": str(e)
        })
        
@router.put("/{short_code}")
async def update_short_code(
    original_url: str, 
    short_code: str,
    user: User = Depends(current_active_user),# только зарегистрированные пользователи могут удалять ссылки
    session: AsyncSession = Depends(get_async_session)
):
    try:
        # проверяем, есть ли укороченная ссылка в базе данных
        query = select(Link).where(Link.shortened_link == short_code)
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing: # если укороченная ссылка уже существует
            raise HTTPException(status_code=409, detail="Short code already exists")
        #проверяем, есть ли оригинальная ссылка в базе данных
        query = select(Link).where(Link.original_link == original_url)
        result = await session.execute(query)
        original_url_existing = result.scalar_one_or_none()
        
        if not original_url_existing: 
            raise HTTPException(status_code=404, detail="Original URL provided not found")
        
        query = update(Link).where(Link.original_link == original_url).values(shortened_link=short_code)
        await session.execute(query)
        await session.commit()
        
        # Чистим кэш для данного short_code
        await redis_client.delete(f"cached_link:{short_code}")
        
        return {"status": "success"}

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error": str(e)
        })
    
@router.get("/{short_code}/stats")
async def get_stats(
    short_code: str,
    original_link_object = Depends(get_link_by_short_code)
):
    '''Получение статистики переходов по ссылке'''
    return {
        "original_link": original_link_object.original_link,
        "created_at": original_link_object.created_at,
        "used_count": original_link_object.used_count,
        "last_used": original_link_object.last_used
    }

# Подключаем роутер к приложению
app.include_router(router)