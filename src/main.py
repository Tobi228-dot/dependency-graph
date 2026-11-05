"""CLI получения прямых зависимостей npm: этап 2."""

import argparse
import configparser
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

if __package__:
    from .registry import RegistryError, get_dependencies
else:
    from registry import RegistryError, get_dependencies


PACKAGE = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9][a-z0-9._-]*")
VERSION = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
FIELDS = {"package", "repository", "test_mode", "version", "output"}


class ConfigError(ValueError):
    """Ошибка пользовательской конфигурации."""


@dataclass(frozen=True)
class Settings:
    """Проверенные настройки приложения."""

    package: str
    repository: str
    test_mode: bool
    version: str
    output: str


def read_section(path):
    """Прочитать UTF-8 INI и проверить набор секций и ключей."""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as error:
        raise ConfigError(f"Не удалось прочитать INI: {error}") from error
    if parser.sections() != ["app"] or parser.defaults():
        raise ConfigError("Нужна единственная секция [app], без DEFAULT")
    section = parser["app"]
    missing = FIELDS - set(section)
    extra = set(section) - FIELDS
    if missing or extra:
        raise ConfigError(
            f"Отсутствуют ключи: {sorted(missing)}; "
            f"неизвестные ключи: {sorted(extra)}"
        )
    for key in FIELDS:
        if not section[key].strip():
            raise ConfigError(f"{key}: значение не должно быть пустым")
    return section


def validate_package(package, test_mode):
    """Проверить npm-имя либо заглавное имя тестового пакета."""
    pattern = r"[A-Z]+" if test_mode else PACKAGE
    if not re.fullmatch(pattern, package):
        raise ConfigError("package: неверное имя пакета")


def validate_version(version):
    """Проверить конкретную версию SemVer, исключая диапазоны."""
    if not VERSION.fullmatch(version):
        raise ConfigError("version: ожидается версия SemVer, например 1.2.3")
    prerelease = version.split("+", 1)[0].partition("-")[2]
    for part in prerelease.split("."):
        if part.isdigit() and part != str(int(part)):
            raise ConfigError("version: ведущие нули в prerelease запрещены")


def local_path(value, base):
    """Разрешить относительный путь от каталога INI-файла."""
    path = Path(value)
    return path if path.is_absolute() else base / path


def validate_test_file(repository, base):
    """Проверить доступность файла тестового репозитория."""
    path = local_path(repository, base)
    try:
        with path.open("rb"):
            pass
    except OSError as error:
        message = f"repository: файл недоступен: {error}"
        raise ConfigError(message) from error


def validate_repository_url(repository):
    """Проверить синтаксис адреса HTTP(S)-репозитория."""
    try:
        url = urlsplit(repository)
        checks = (
            url.scheme in {"http", "https"},
            bool(url.hostname),
            not any(char.isspace() for char in repository),
            url.username is None,
            url.password is None,
            url.port is None or url.port > 0,
            not url.fragment,
            not url.query,
        )
    except ValueError as error:
        raise ConfigError("repository: некорректный URL") from error
    if not all(checks):
        raise ConfigError("repository: нужен HTTP(S) URL без учётных данных")


def validate_repository(repository, test_mode, base):
    """Выбрать проверку тестового файла или адреса репозитория."""
    if test_mode:
        validate_test_file(repository, base)
    else:
        validate_repository_url(repository)


def validate_output(output, base):
    """Проверить имя SVG и существование родительского каталога."""
    path = local_path(output, base)
    if path.suffix.lower() != ".svg" or "\x00" in output:
        raise ConfigError("output: нужно имя файла с расширением .svg")
    if path.exists() and not path.is_file():
        raise ConfigError("output: путь указывает не на обычный файл")
    if not path.parent.is_dir():
        raise ConfigError("output: родительский каталог не существует")


def load_settings(path):
    """Прочитать и проверить все пять пользовательских параметров."""
    section = read_section(path)
    try:
        test_mode = section.getboolean("test_mode")
    except ValueError as error:
        raise ConfigError("test_mode: нужно true/false, yes/no, on/off, 1/0") \
            from error
    settings = Settings(
        section["package"], section["repository"], test_mode,
        section["version"], section["output"],
    )
    validate_package(settings.package, test_mode)
    validate_version(settings.version)
    validate_repository(settings.repository, test_mode, path.parent)
    validate_output(settings.output, path.parent)
    return settings


def main(argv=None):
    """Вывести прямые зависимости; вернуть 2 при пользовательской ошибке."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="путь к UTF-8 INI-файлу")
    arguments = parser.parse_args(argv)
    try:
        settings = load_settings(arguments.config)
        dependencies = get_dependencies(settings, arguments.config.parent)
    except ConfigError as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        return 2
    except RegistryError as error:
        print(f"Ошибка репозитория: {error}", file=sys.stderr)
        return 2
    print(f"Прямые зависимости {settings.package}@{settings.version}:")
    if not dependencies:
        print("Прямых зависимостей нет")
    for name, constraint in dependencies.items():
        print(f"{name}={constraint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
