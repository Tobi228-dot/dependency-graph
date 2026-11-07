"""Проверки BFS, циклов, тестовых файлов и версий npm-узлов."""

import contextlib
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.graph import bfs_graph, build_graph
from src.main import Settings, main
from src.registry import RegistryError


SETTINGS = Settings("A", "repo.json", True, "1.0.0", "graph.svg")


class GraphTests(unittest.TestCase):
    """Проверять порядок обхода и сохранение всех достижимых связей."""

    def test_breadth_first_order(self):
        """Дочерние узлы обрабатываются по уровням, а не в глубину."""
        source = {"A": ["B", "C"], "B": ["D"], "C": ["E"],
                  "D": [], "E": [], "Z": []}
        graph = bfs_graph("A", source.__getitem__)
        self.assertEqual(list(graph), ["A", "B", "C", "D", "E"])
        self.assertEqual(graph["A"], ("B", "C"))
        self.assertNotIn("Z", graph)

    def test_cycles_and_shared_nodes(self):
        """Циклы, самоссылка и общий узел не вызывают повторной загрузки."""
        source = {"A": ["A", "B", "C"], "B": ["D"],
                  "C": ["D"], "D": ["A"]}
        loader = unittest.mock.Mock(side_effect=source.__getitem__)
        graph = bfs_graph("A", loader)
        self.assertEqual(loader.call_count, len(source))
        self.assertEqual(graph["A"], ("A", "B", "C"))
        self.assertEqual(graph["D"], ("A",))
        self.assertEqual(graph["B"], graph["C"])

    def test_long_chain_without_recursion(self):
        """Глубокая цепочка превышает обычный предел рекурсии Python."""
        length = 1500
        graph = bfs_graph(0, lambda node: [node + 1] if node < length else [])
        self.assertEqual(len(graph), length + 1)
        self.assertEqual(graph[length], ())

    def test_example_files(self):
        """Все поставляемые тестовые репозитории строятся через CLI."""
        for name in ("chain", "branch", "cycle", "self", "empty"):
            with self.subTest(name=name):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["--config", f"examples/{name}.ini"])
                self.assertEqual(code, 0)
                self.assertIn("Граф зависимостей (BFS):", output.getvalue())
        self.assertIn("A -> нет зависимостей", output.getvalue())

    def test_missing_transitive_node(self):
        """Ссылка на отсутствующий тестовый узел даёт понятную ошибку."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "repo.json").write_text('{"A": ["B"]}')
            with self.assertRaisesRegex(RegistryError, "не найден"):
                build_graph(SETTINGS, base)

    def test_local_source_is_read_once(self):
        """Весь тестовый файл читается один раз, без сетевых запросов."""
        source = {"A": ["B"], "B": ["A"]}
        with patch("src.graph.read_test_graph", return_value=source) as read:
            with patch("src.registry.urlopen") as network:
                graph = build_graph(SETTINGS, Path("."))
        read.assert_called_once()
        network.assert_not_called()
        self.assertEqual(graph, {"A": ("B",), "B": ("A",)})

    def test_npm_versions_cycles_and_cache(self):
        """Различать версии, сохранять циклы и кешировать каталоги."""
        root = {"name": "app", "version": "1.0.0",
                "dependencies": {"b": "^1", "c": "1.0.0"}}
        catalogues = {
            "app": {"versions": {"1.0.0": root}},
            "b": {"versions": {"1.2.0": {
                "name": "b", "version": "1.2.0",
                "dependencies": {"app": "1.0.0", "d": "^1"}}}},
            "c": {"versions": {"1.0.0": {
                "name": "c", "version": "1.0.0",
                "dependencies": {"d": "^2"}}}},
            "d": {"versions": {
                "1.0.0": {"name": "d", "version": "1.0.0"},
                "2.0.0": {"name": "d", "version": "2.0.0"}}},
        }
        settings = replace(SETTINGS, package="app", test_mode=False,
                           repository="https://registry.npmjs.org")
        with patch("src.graph.fetch_metadata", return_value=root) as fetch:
            with patch("src.graph.fetch_catalogue",
                       side_effect=lambda _, name: catalogues[name]) as cat:
                graph = build_graph(settings, Path("."))
        fetch.assert_called_once()
        self.assertEqual(cat.call_count, len(catalogues))
        self.assertEqual(list(graph), ["app@1.0.0", "b@1.2.0", "c@1.0.0",
                                      "d@1.0.0", "d@2.0.0"])
        self.assertIn("app@1.0.0", graph["b@1.2.0"])

    def test_unsatisfied_dependency(self):
        """Неразрешимый диапазон не превращается в потерянную связь."""
        root = {"name": "app", "version": "1.0.0",
                "dependencies": {"b": "^2"}}
        catalogue = {"versions": {"1.0.0": {}}}
        settings = replace(SETTINGS, package="app", test_mode=False)
        with patch("src.graph.fetch_metadata", return_value=root):
            with patch("src.graph.fetch_catalogue", return_value=catalogue):
                with self.assertRaisesRegex(RegistryError, "Нет версии"):
                    build_graph(settings, Path("."))


if __name__ == "__main__":
    unittest.main()
