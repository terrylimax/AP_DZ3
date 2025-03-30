import re
from links.router import generate_short_url
from auth.users import get_jwt_strategy

def test_generate_short_url_unique():
    # Генерируем 100 коротких URL и проверяем, что все они уникальны
    urls = [generate_short_url() for _ in range(100)]
    unique_urls = set(urls)
    assert len(unique_urls) == len(urls), "Generated short URLs must be unique."

def test_generate_short_url_alphanumeric():
    short_url = generate_short_url()
    # Проверяем, что сгенерированный URL состоит только из латинских букв и цифр
    pattern = r'^[A-Za-z0-9]{6}$'
    assert re.match(pattern, short_url), "Short URL must be alphanumeric and 6 characters long."

def test_get_jwt_strategy_instance():
    strategy = get_jwt_strategy()
    # Проверяем, что возвращённая стратегия имеет, например, атрибут secret
    assert hasattr(strategy, "secret"), "JWT strategy should have a secret attribute."