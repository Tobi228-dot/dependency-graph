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


def fetch_json(url):
    """Получить JSON по HTTP(S), обработав сетевые ошибки."""
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


def fetch_metadata(settings):
    """Запросить метаданные точной версии npm-пакета по HTTP(S)."""
    package = quote(settings.package, safe="")
    version = quote(settings.version, safe="")
    url = f"{settings.repository.rstrip('/')}/{package}/{version}"
    return fetch_json(url)


def fetch_catalogue(settings, package):
    """Получить опубликованные версии пакета для разрешения диапазонов."""
    url = f"{settings.repository.rstrip('/')}/{quote(package, safe='')}"
    data = fetch_json(url)
    if not isinstance(data.get("versions"), dict):
        raise RegistryError(f"Нет списка версий пакета {package}")
    if not isinstance(data.get("dist-tags", {}), dict):
        raise RegistryError(f"Некорректные dist-tags пакета {package}")
    return data


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


def read_test_graph(settings, base):
    """Прочитать файл тестового графа вида A: [B, C]."""
    path = Path(settings.repository)
    if not path.is_absolute():
        path = base / path
    try:
        with path.open("rb") as stream:
            graph = read_json(stream)
    except OSError as error:
        raise RegistryError(f"Не удалось прочитать тестовый файл: {error}") \
            from error
    return graph


def test_children(graph, package):
    """Проверить имя и получить прямые связи тестового узла."""
    if not re.fullmatch(r"[A-Z]+", package):
        raise RegistryError("Тестовые имена: заглавные латинские буквы")
    if package not in graph:
        raise RegistryError("Пакет не найден в тестовом репозитории")
    dependencies = graph[package]
    if not isinstance(dependencies, list):
        raise RegistryError("Зависимости тестового пакета должны быть списком")
    for name in dependencies:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z]+", name):
            raise RegistryError("Тестовые имена: заглавные латинские буквы")
    return dict.fromkeys(sorted(dependencies), "*")


def read_test_dependencies(settings, base):
    """Прочитать прямые связи заданного тестового пакета."""
    return test_children(read_test_graph(settings, base), settings.package)


def get_dependencies(settings, base):
    """Получить прямые зависимости из npm или локального тестового файла."""
    if settings.test_mode:
        return read_test_dependencies(settings, base)
    return extract_dependencies(fetch_metadata(settings), settings)
