"""Получение прямых зависимостей средствами стандартной библиотеки."""

import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REQUEST_TIMEOUT = 15
HTTP_NOT_FOUND = 404


class RegistryError(ValueError):
    """Ошибка получения или разбора данных репозитория."""


def read_json(stream):
    """Разобрать JSON-объект, отклоняя ошибочную кодировку и структуру."""
    try:
        data = json.loads(stream.read().decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise RegistryError("Репозиторий вернул некорректный JSON") from error
    if not isinstance(data, dict):
        raise RegistryError("Ожидался JSON-объект репозитория")
    return data


def fetch_metadata(settings):
    """Запросить метаданные точной версии npm-пакета по HTTP(S)."""
    package = quote(settings.package, safe="")
    version = quote(settings.version, safe="")
    url = f"{settings.repository.rstrip('/')}/{package}/{version}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return read_json(response)
    except HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            message = "Пакет или указанная версия не найдены (HTTP 404)"
        else:
            message = f"Ошибка репозитория: HTTP {error.code}"
        raise RegistryError(message) from error
    except (URLError, OSError) as error:
        raise RegistryError(f"Не удалось получить метаданные: {error}") \
            from error


def extract_dependencies(metadata, settings):
    """Проверить пакет и версию, извлечь только поле dependencies."""
    if metadata.get("name") != settings.package:
        raise RegistryError("В ответе другое имя пакета")
    if metadata.get("version") != settings.version:
        raise RegistryError("В ответе другая версия пакета")
    dependencies = metadata.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise RegistryError("Поле dependencies должно быть объектом")
    for name, constraint in dependencies.items():
        if not isinstance(constraint, str) or not name or not constraint:
            raise RegistryError("Некорректное описание зависимости")
    return dict(sorted(dependencies.items()))


def read_test_dependencies(settings, base):
    """Прочитать прямые связи из тестового графа вида A: [B, C]."""
    path = Path(settings.repository)
    if not path.is_absolute():
        path = base / path
    try:
        with path.open("rb") as stream:
            graph = read_json(stream)
    except OSError as error:
        raise RegistryError(f"Не удалось прочитать тестовый файл: {error}") \
            from error
    if settings.package not in graph:
        raise RegistryError("Пакет не найден в тестовом репозитории")
    dependencies = graph[settings.package]
    if not isinstance(dependencies, list):
        raise RegistryError("Зависимости тестового пакета должны быть списком")
    for name in dependencies:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z]+", name):
            raise RegistryError("Тестовые имена: заглавные латинские буквы")
    return dict.fromkeys(sorted(dependencies), "*")


def get_dependencies(settings, base):
    """Получить прямые зависимости из npm или локального тестового файла."""
    if settings.test_mode:
        return read_test_dependencies(settings, base)
    return extract_dependencies(fetch_metadata(settings), settings)
