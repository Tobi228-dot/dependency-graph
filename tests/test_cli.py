"""Проверки конфигурации и запуска CLI первого этапа."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from src.main import ConfigError, load_settings, main


class ConfigTests(unittest.TestCase):
    """Проверять корректные настройки и ошибки каждого параметра."""

    def setUp(self):
        """Создать изолированную конфигурацию."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.path = self.base / "config.ini"
        self.values = {
            "package": "express",
            "repository": "https://registry.npmjs.org",
            "test_mode": "false",
            "version": "4.18.2",
            "output": "graph.svg",
        }

    def write_config(self):
        """Сохранить текущие тестовые настройки."""
        lines = ["[app]"]
        lines.extend(f"{key}={value}" for key, value in self.values.items())
        self.path.write_text("\n".join(lines), encoding="utf-8")

    def test_valid_configuration(self):
        """Обычный и scoped npm-пакеты принимаются."""
        for package in ("express", "@types/node"):
            self.values["package"] = package
            self.write_config()
            settings = load_settings(self.path)
            self.assertEqual(settings.package, package)
            self.assertFalse(settings.test_mode)

    def test_test_repository_relative_to_config(self):
        """Относительный путь относится к INI, а не к рабочему каталогу."""
        (self.base / "repo.json").write_text("{}", encoding="utf-8")
        self.values.update(package="ABC", test_mode="true",
                           repository="repo.json")
        self.write_config()
        self.assertTrue(load_settings(self.path).test_mode)

    def test_invalid_values(self):
        """Каждый параметр отклоняет некорректные значения."""
        cases = {
            "package": ["Bad Name", "@scope/", "../foo"],
            "repository": ["ftp://example.org", "https://", "https://a:bad"],
            "test_mode": ["maybe"],
            "version": ["latest", "^1.0.0", "01.2.3", "1.0.0-01"],
            "output": ["graph.png", "missing/graph.svg"],
        }
        for key, values in cases.items():
            original = self.values[key]
            for value in values:
                with self.subTest(key=key, value=value):
                    self.values[key] = value
                    self.write_config()
                    with self.assertRaisesRegex(ConfigError, key):
                        load_settings(self.path)
            self.values[key] = original

    def test_missing_and_empty_parameters(self):
        """Каждый ключ обязателен и не может иметь пустое значение."""
        for key in list(self.values):
            original = self.values.pop(key)
            self.write_config()
            with self.assertRaisesRegex(ConfigError, key):
                load_settings(self.path)
            self.values[key] = ""
            self.write_config()
            with self.assertRaisesRegex(ConfigError, key):
                load_settings(self.path)
            self.values[key] = original

    def test_invalid_test_repository(self):
        """Тестовый источник должен существовать и быть файлом."""
        self.values.update(package="A", test_mode="true")
        for source in ("missing.json", "."):
            self.values["repository"] = source
            self.write_config()
            with self.assertRaisesRegex(ConfigError, "repository"):
                load_settings(self.path)

    def test_output_directory(self):
        """Каталог с именем SVG не считается выходным файлом."""
        (self.base / "graph.svg").mkdir()
        self.write_config()
        with self.assertRaisesRegex(ConfigError, "output"):
            load_settings(self.path)

    def test_ini_errors(self):
        """Ошибки формата, секций и неизвестные ключи диагностируются."""
        for content in ("invalid", "[other]\nx=1", "[app]\nx=1",
                        "[app]\npackage=a\npackage=b",
                        "[DEFAULT]\nx=1\n[app]\n"):
            self.path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_settings(self.path)

    def test_missing_and_non_utf8_file(self):
        """Отсутствующий файл и неверная кодировка обработаны."""
        with self.assertRaises(ConfigError):
            load_settings(self.path)
        self.path.write_bytes(b"\xff")
        with self.assertRaises(ConfigError):
            load_settings(self.path)

    def test_cli_output(self):
        """CLI выводит все пять пар ключ-значение."""
        self.write_config()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--config", str(self.path)])
        self.assertEqual(code, 0)
        expected = {f"{key}={value}" for key, value in self.values.items()}
        self.assertEqual(set(output.getvalue().splitlines()), expected)

    def test_cli_error(self):
        """Ошибка даёт код 2, понятное сообщение и не даёт traceback."""
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = main(["--config", str(self.path)])
        self.assertEqual(code, 2)
        self.assertIn("Ошибка конфигурации", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
