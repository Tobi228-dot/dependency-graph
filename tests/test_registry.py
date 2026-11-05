"""Проверки протокола npm, данных и ошибок второго этапа."""

from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.main import Settings, main
from src.registry import (
    RegistryError, extract_dependencies, fetch_metadata, get_dependencies,
    read_json,
)


SETTINGS = Settings("express", "https://registry.npmjs.org", False,
                    "4.18.2", "graph.svg")


class RegistryTests(unittest.TestCase):
    """Проверять реальные форматы ответов без внешней сети."""

    def test_exact_version_request(self):
        """Запрос содержит заданную версию, базовый путь и scoped-имя."""
        settings = replace(SETTINGS, package="@types/node", version="20.0.0",
                           repository="https://example.org/npm/")
        data = {"name": "@types/node", "version": "20.0.0"}
        stream = io.BytesIO(json.dumps(data).encode())
        with patch("src.registry.urlopen", return_value=stream) as request:
            self.assertEqual(fetch_metadata(settings), data)
        args, kwargs = request.call_args
        self.assertEqual(args[0].full_url,
                         "https://example.org/npm/%40types%2Fnode/20.0.0")
        self.assertEqual(kwargs["timeout"], 15)

    def test_only_direct_runtime_dependencies(self):
        """Dev/peer/optional-поля не подмешиваются в dependencies."""
        data = {
            "name": "express", "version": "4.18.2",
            "dependencies": {"z": "^2", "a": "~1"},
            "devDependencies": {"dev": "*"},
            "peerDependencies": {"peer": "*"},
            "optionalDependencies": {"optional": "*"},
        }
        with patch("src.registry.fetch_metadata", return_value=data):
            result = get_dependencies(SETTINGS, Path("."))
        self.assertEqual(result, {"a": "~1", "z": "^2"})
        self.assertEqual(list(result), ["a", "z"])

    def test_no_dependencies(self):
        """Пакет без dependencies даёт пустой результат."""
        data = {"name": "express", "version": "4.18.2"}
        self.assertEqual(extract_dependencies(data, SETTINGS), {})

    def test_wrong_metadata(self):
        """Неверная версия, имя и структура зависимостей отклоняются."""
        valid = {"name": "express", "version": "4.18.2"}
        for changes in ({"name": "other"}, {"version": "1.0.0"},
                        {"dependencies": []}, {"dependencies": {"a": 2}},
                        {"dependencies": {"": "*"}}):
            with self.subTest(changes=changes):
                with self.assertRaises(RegistryError):
                    extract_dependencies(valid | changes, SETTINGS)

    def test_json_errors(self):
        """Некорректные JSON, UTF-8 и тип корня отклоняются."""
        for content in (b"bad", b"\xff", b"[]", b"null"):
            with self.assertRaises(RegistryError):
                read_json(io.BytesIO(content))

    def test_network_errors(self):
        """HTTP 404/500, сбой соединения и таймаут обработаны."""
        errors = [
            HTTPError("https://example.org", 404, "missing", {}, None),
            HTTPError("https://example.org", 500, "error", {}, None),
            URLError("offline"), TimeoutError("timeout"),
        ]
        for error in errors:
            with self.subTest(error=error):
                with patch("src.registry.urlopen", side_effect=error):
                    with self.assertRaises(RegistryError):
                        fetch_metadata(SETTINGS)

    def test_local_graph(self):
        """Тестовый граф даёт прямые связи и ошибку отсутствующего узла."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "repo.json"
            path.write_text('{"A": ["B", "C"], "B": []}')
            settings = replace(SETTINGS, package="A", test_mode=True,
                               repository="repo.json")
            self.assertEqual(get_dependencies(settings, base),
                             {"B": "*", "C": "*"})
            empty = replace(settings, package="B")
            self.assertEqual(get_dependencies(empty, base), {})
            with self.assertRaises(RegistryError):
                get_dependencies(replace(settings, package="Z"), base)

    def test_invalid_local_graph(self):
        """Тестовый граф должен содержать списки заглавных имён."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            settings = replace(SETTINGS, package="A", test_mode=True,
                               repository="repo.json")
            for value in ({}, [2], ["lower"], ["Б"]):
                (base / "repo.json").write_text(json.dumps({"A": value}))
                with self.assertRaises(RegistryError):
                    get_dependencies(settings, base)

    def test_cli_registry_error(self):
        """CLI возвращает код 2 при ошибке сервера без traceback."""
        import contextlib

        errors = io.StringIO()
        with patch("src.main.get_dependencies",
                   side_effect=RegistryError("HTTP 404")):
            with contextlib.redirect_stderr(errors):
                code = main(["--config", "examples/config.ini"])
        self.assertEqual(code, 2)
        self.assertIn("HTTP 404", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
