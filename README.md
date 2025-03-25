# URL Shortener API

## Описание API
Этот проект предоставляет REST API для создания, перенаправления, удаления и обновления сокращённых ссылок.
- **POST /links/shorten** — создание новой короткой ссылки.
- **GET /links/{short_code}** — перенаправление на оригинальный URL по короткому коду.
- **DELETE /links/{short_code}** — удаление ссылки (требуется авторизация).
- **PUT /links/{short_code}** — изменение укороченной ссылки (требуется авторизация).
- **GET /links/{short_code}/stats** — получение статистики использования ссылки.
- **GET /links/search?original_url=<URL>** — поиск ссылок по оригинальному URL.

## Примеры запросов

### Создание короткой ссылки
Пример запроса через curl:
```
curl -X POST "http://localhost:8000/links/shorten" \
  -d "original_link=https://example.com" \
  -d "custom_alias=myalias"
```

### Перенаправление по короткому коду
Пример запроса:
```
curl -L "http://localhost:8000/links/myalias"
или в браузере в адресной строке "localhost:8000/links/myalias"
```

### Удаление ссылки (авторизация требуется)
Пример запроса:
```
curl -X DELETE "http://localhost:8000/links/myalias" \
  -H "Authorization: Bearer <your_token>"
```

### Получение статистики
Пример запроса:
```
curl "http://localhost:8000/links/myalias/stats"
```

## Инструкция по запуску

1. Клонируйте репозиторий.
2. Создайте базу данных в PostgreSQL, создайте файл `.env` и настройте переменные 
окружения для подключения к ней:
   - DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME
3. Установите зависимости:
   ```
   pip install -r requirements.txt
   ```
4. Запустите сервер PostgreSQL и Redis.
5. Таблицы должны создаваться автоматически при запуске приложения 
6. Запустите приложение:
   Если вы находитесь в директории проекта (где находится main.py):
   ```
   uvicorn main:app --reload
   ```

7. Запустите Celery Flower для мониторинга очередей (в отдельном терминале):
   ```
   celery -A tasks.tasks flower
   ```
8. Запустите Celery worker c поддержкой beat для периодических задач (в ещё одном терминале):
   ```
   celery -A tasks.tasks worker --beat --loglevel=info
   ```

## Описание базы данных

### Таблица links
- **id**: UUID — уникальный идентификатор ссылки.
- **user_id**: UUID (может быть NULL) — идентификатор пользователя (если создана зарегистрированным пользователем).
- **original_link**: String — оригинальный URL (уникальное поле).
- **shortened_link**: String — сгенерированный или заданный пользователем короткий код (уникальное поле).
- **created_at**: DateTime — дата и время создания записи.
- **last_used**: DateTime — дата и время последнего использования ссылки.
- **custom_alias**: Boolean — флаг, указывающий, установлен ли кастомный alias.
- **expires_at**: DateTime (опционально) — время истечения срока действия ссылки.
- **used_count**: Integer — счетчик использования ссылки.

Также используется таблица пользователей, управляемая fastapi-users, для аутентификации и авторизации:

### Таблица users
- **id**
- **email**
- **hashed_password**
- **is_active**
- **is_superuser**
- **is_verified**