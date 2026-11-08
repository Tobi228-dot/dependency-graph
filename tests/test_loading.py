"""Проверки порядка загрузки и режима CLI."""

import contextlib
import io
import unittest

from src.loading import loading_order
from src.main import main
from src.registry import RegistryError


class LoadingTests(unittest.TestCase):
    """Проверять порядок зависимостей, общие узлы, циклы и вывод CLI."""

    def test_chain(self):
        """Каждая зависимость цепочки предшествует своему потребителю."""
        graph = {"A": ("B",), "B": ("C",), "C": ()}
        self.assertEqual(loading_order(graph), ["C", "B", "A"])

    def test_shared_dependency(self):
        """Общий пакет выводится один раз и раньше обоих потребителей."""
        graph = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        self.assertEqual(loading_order(graph), ["D", "B", "C", "A"])

    def test_all_edges_are_respected(self):
        """Проверить порядок для разных уровней и перекрёстных связей."""
        graph = {"A": ("B", "C"), "B": ("D", "E"), "C": ("E",),
                 "D": ("F",), "E": (), "F": ()}
        result = loading_order(graph)
        positions = {node: index for index, node in enumerate(result)}
        self.assertEqual(set(result), set(graph))
        for node, dependencies in graph.items():
            for dependency in dependencies:
                self.assertLess(positions[dependency], positions[node])

    def test_empty_and_single_package(self):
        """Пакет без зависимостей входит в результат сам."""
        self.assertEqual(loading_order({}), [])
        self.assertEqual(loading_order({"A": ()}), ["A"])

    def test_duplicate_edges(self):
        """Повтор одной связи не блокирует завершение сортировки."""
        self.assertEqual(loading_order({"A": ("B", "B"), "B": ()}),
                         ["B", "A"])

    def test_versioned_nodes(self):
        """Две версии одного пакета остаются разными узлами."""
        graph = {"a@1.0.0": ("b@1.0.0", "b@2.0.0"),
                 "b@1.0.0": (), "b@2.0.0": ()}
        self.assertEqual(loading_order(graph),
                         ["b@1.0.0", "b@2.0.0", "a@1.0.0"])

    def test_cycles(self):
        """Цикл и самоссылка не имеют корректного топологического порядка."""
        for graph in ({"A": ("A",)}, {"A": ("B",), "B": ("A",)},
                      {"A": ("B", "C"), "B": ("B",), "C": ()}):
            with self.assertRaisesRegex(RegistryError, "Циклические"):
                loading_order(graph)

    def test_missing_node(self):
        """Неполный граф отклоняется с указанием отсутствующего пакета."""
        with self.assertRaisesRegex(RegistryError, "отсутствует узел B"):
            loading_order({"A": ("B",)})

    def test_long_chain(self):
        """Порядок глубокой цепочки вычисляется без рекурсии."""
        length = 1500
        graph = {node: (node + 1,) for node in range(length)}
        graph[length] = ()
        expected = list(reversed(range(length + 1)))
        self.assertEqual(loading_order(graph), expected)

    def test_cli_examples(self):
        """Режим CLI выводит ожидаемый порядок для тестовых файлов."""
        cases = {"chain": ["C", "B", "A"],
                 "branch": ["D", "B", "C", "A"], "empty": ["A"]}
        for name, expected in cases.items():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--config", f"examples/{name}.ini",
                             "--load-order"])
            self.assertEqual(code, 0)
            lines = output.getvalue().splitlines()
            self.assertEqual(lines[1:], [f"{i}. {node}" for i, node in
                                        enumerate(expected, start=1)])

    def test_cli_cycle_error(self):
        """При цикле нет частичного порядка или traceback, код завершения 2."""
        for name in ("cycle", "self"):
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output):
                with contextlib.redirect_stderr(errors):
                    code = main(["--config", f"examples/{name}.ini",
                                 "--load-order"])
            self.assertEqual(code, 2)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("Циклические зависимости", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
