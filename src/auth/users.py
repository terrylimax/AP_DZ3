import uuid
from typing import Optional
from fastapi import Depends, Request
# Импорт базовых классов для управления пользователями из fastapi-users
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

from .db import User, get_user_db  # Импорт модели пользователя и функции доступа к базе данных

SECRET = "SECRET"  # Секрет, используемый для подписывания JWT-токенов и генерации токенов сброса пароля

# Определяем менеджер пользователей, реализующий необходимую логику
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    # Секреты для токенов сброса пароля и верификации нового пользователя
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    # Метод, вызываемый после успешной регистрации пользователя
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    # Метод, вызываемый после запроса сброса пароля
    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    # Метод, вызываемый после запроса верификации аккаунта
    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")

# Функция-зависимость для получения инстанса менеджера пользователей
async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

# Настройка транспорта для аутентификации Bearer Token
# tokenUrl указывает URL для логина, где клиент получает токен.
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# Функция, которая возвращает стратегию JWT для подписи и проверки токенов.
# Важно, чтобы типы (User, uuid.UUID) соответствовали используемым в FastAPIUsers.
def get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

# Настройка бекенда аутентификации, который использует JWT токен через Bearer транспорт.
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Инициализация FastAPIUsers, где:
# - User: модель пользователя
# - uuid.UUID: тип идентификатора
# - get_user_manager: функция-зависимость для получения менеджера пользователей
# - [auth_backend]: список бекендов аутентификации, которые будут использоваться
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Зависимость, возвращающая текущего активного пользователя.
# Может использоваться в роутерах для защиты эндпоинтов.
current_active_user = fastapi_users.current_user(active=True)

async def get_optional_current_user(request: Request) -> Optional[User]:
    try:
        # Пытаемся получить текущего активного пользователя.
        return await current_active_user(request)
    except Exception:
        # Если аутентификация не прошла, возвращаем None
        return None