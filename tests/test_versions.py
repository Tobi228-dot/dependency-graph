"""Проверки ограничений версий, используемых в зависимостях npm."""

import unittest

from src.versions import VersionError, select_version, version_key


class VersionTests(unittest.TestCase):
    """Проверять числовое сравнение, диапазоны и prerelease."""

    def test_ranges(self):
        """Выбирается наибольшая подходящая версия, а не строковый максимум."""
        versions = ["0.0.1", "0.0.2", "0.1.0", "0.2.0", "1.0.0", "1.2.0",
                    "1.2.3", "1.2.10", "1.3.0", "2.0.0", "10.0.0"]
        cases = {
            "1.2.3": "1.2.3", "v1.2.3": "1.2.3", "=1.2.3": "1.2.3",
            "*": "10.0.0", "1": "1.3.0", "1.2.x": "1.2.10",
            "^1.2.0": "1.3.0", "~1.2.0": "1.2.10", "~1": "1.3.0",
            "^0.1.0": "0.1.0", "^0.0.1": "0.0.1", "^0.0": "0.0.2",
            ">= 1.2.3 < 2": "1.3.0", "<=1.2": "1.2.10",
            ">1.2 <2": "1.3.0", "<1.2": "1.0.0",
            "1.0.0 - 1.2.3": "1.2.3", "1 - 1.2": "1.2.10",
            "^0.1 || ~1.2": "1.2.10", "1.2.*": "1.2.10",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(select_version(versions, expression), expected)

    def test_prerelease(self):
        """Prerelease исключаются без явного запроса соответствующего core."""
        versions = ["1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0-beta",
                    "1.0.0", "1.1.0-alpha"]
        self.assertEqual(select_version(versions, "*"), "1.0.0")
        self.assertEqual(select_version(versions, ">=1.0.0-alpha <1.0.0"),
                         "1.0.0-beta")
        self.assertLess(version_key("1.0.0-alpha.2"),
                        version_key("1.0.0-alpha.10"))
        self.assertEqual(version_key("1.0.0+a"), version_key("1.0.0+b"))

    def test_dist_tags(self):
        """Метка реестра разрешается в конкретную версию."""
        tags = {"latest": "1.2.3", "next": "2.0.0-beta.1"}
        versions = ["1.2.3", "2.0.0-beta.1"]
        self.assertEqual(select_version(versions, "latest", tags), "1.2.3")
        self.assertEqual(select_version(versions, "next", tags), "2.0.0-beta.1")

    def test_invalid_or_missing_versions(self):
        """Неподдерживаемые источники и пустой выбор дают явную ошибку."""
        for expression in ("^2", "file:../local", "git+https://example.org/a",
                           "1.*.2", "garbage", "1.0.0-01"):
            with self.subTest(expression=expression):
                with self.assertRaises(VersionError):
                    select_version(["1.0.0"], expression)
        self.assertEqual(select_version(["invalid", "1.0.0"], "*"), "1.0.0")


if __name__ == "__main__":
    unittest.main()
