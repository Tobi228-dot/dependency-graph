"""Проверки PlantUML, SVG, ошибок рендеринга и режима CLI."""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.main import Settings, main
from src.visualization import (
    VisualizationError, escape_label, plantuml_command, plantuml_source,
    render_svg, save_visualization, validate_svg,
)


SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>'


class VisualizationTests(unittest.TestCase):
    """Проверять сохранение структуры графа и обработку внешнего процесса."""

    def test_graph_source(self):
        """Все версии и scoped-имена имеют отдельные алиасы и связи."""
        graph = {"app@1.0.0": ("@scope/pkg@2.0.0", "pkg@1.0.0"),
                 "@scope/pkg@2.0.0": (), "pkg@1.0.0": ()}
        source = plantuml_source(graph)
        self.assertTrue(source.startswith("@startuml\n"))
        self.assertTrue(source.endswith("@enduml\n"))
        self.assertIn('rectangle "@scope/pkg@2.0.0" as n1', source)
        self.assertIn("n0 --> n1", source)
        self.assertIn("n0 --> n2", source)
        self.assertEqual(source.count("rectangle "), len(graph))

    def test_cycles_and_shared_nodes(self):
        """Цикл, самоссылка и общий узел сохраняются на диаграмме."""
        graph = {"A": ("A", "B", "C"), "B": ("C",), "C": ("A",)}
        source = plantuml_source(graph)
        self.assertIn("n0 --> n0", source)
        self.assertIn("n1 --> n2", source)
        self.assertIn("n2 --> n0", source)
        self.assertEqual(source.count('rectangle "C"'), 1)

    def test_single_node_and_missing_node(self):
        """Лист отображается; ссылка на отсутствующий узел отклоняется."""
        self.assertIn('rectangle "A" as n0', plantuml_source({"A": ()}))
        with self.assertRaisesRegex(VisualizationError, "Нет узла B"):
            plantuml_source({"A": ("B",)})

    def test_escaping(self):
        """Кавычки, обратные слеши и переводы строк экранируются."""
        self.assertEqual(escape_label('a"b\\c\n@enduml'),
                         'a\\"b\\\\c\\n@enduml')

    def test_jar_selection(self):
        """Путь JAR с пробелами передаётся отдельным аргументом Java."""
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "plant uml.jar"
            jar.write_bytes(b"")
            with patch.dict("os.environ", {"PLANTUML_JAR": str(jar)}):
                with patch("src.visualization.shutil.which",
                           return_value="/usr/bin/java"):
                    command = plantuml_command()
            self.assertEqual(command[-2:], ["-jar", str(jar)])

    def test_missing_plantuml(self):
        """Отсутствующий PlantUML даёт инструкцию по настройке."""
        with patch.dict("os.environ", {"PLANTUML_JAR": ""}):
            with patch("src.visualization.shutil.which", return_value=None):
                with self.assertRaisesRegex(VisualizationError, "Установите"):
                    plantuml_command()

    def test_missing_jar(self):
        """Ошибочный путь JAR даёт понятную ошибку."""
        with patch.dict("os.environ", {"PLANTUML_JAR": "/missing/jar"}):
            with self.assertRaisesRegex(VisualizationError, "файл не найден"):
                plantuml_command()

    def test_missing_java(self):
        """Существующий JAR требует доступную Java."""
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "plantuml.jar"
            jar.write_bytes(b"")
            with patch.dict("os.environ", {"PLANTUML_JAR": str(jar)}):
                with patch("src.visualization.shutil.which", return_value=None):
                    with self.assertRaisesRegex(VisualizationError, "Java"):
                        plantuml_command()

    def test_renderer_process(self):
        """PlantUML получает исходник через stdin; результат проверяется."""
        result = subprocess.CompletedProcess([], 0, stdout=SVG, stderr="")
        with patch("src.visualization.plantuml_command", return_value=["uml"]):
            with patch("src.visualization.subprocess.run",
                       return_value=result) as run:
                self.assertEqual(render_svg("@startuml\n@enduml"), SVG)
        args, kwargs = run.call_args
        self.assertIn("-tsvg", args[0])
        self.assertEqual(kwargs["input"], "@startuml\n@enduml")
        self.assertNotIn("shell", kwargs)

    def test_renderer_errors(self):
        """Сбой процесса, таймаут и ошибка синтаксиса не считаются успехом."""
        for error in (OSError("missing"),
                      subprocess.TimeoutExpired("uml", 60)):
            with patch("src.visualization.plantuml_command", return_value=[]):
                with patch("src.visualization.subprocess.run",
                           side_effect=error):
                    with self.assertRaises(VisualizationError):
                        render_svg("source")
        result = subprocess.CompletedProcess([], 1, stdout=SVG, stderr="bad")
        with patch("src.visualization.plantuml_command", return_value=[]):
            with patch("src.visualization.subprocess.run", return_value=result):
                with self.assertRaisesRegex(VisualizationError, "bad"):
                    render_svg("source")

    def test_svg_validation(self):
        """HTML и повреждённый XML не сохраняются как успешный SVG."""
        validate_svg(SVG)
        for invalid in ("not xml", "<html/>"):
            with self.assertRaises(VisualizationError):
                validate_svg(invalid)

    def test_save_files(self):
        """Оба файла сохраняются рядом с указанным SVG в UTF-8."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "diagram.svg"
            with patch("src.visualization.render_svg", return_value=SVG):
                source_path, svg_path = save_visualization({"A": ()}, target)
            self.assertEqual(source_path, target.with_suffix(".puml"))
            self.assertIn('rectangle "A"', source_path.read_text())
            self.assertEqual(svg_path.read_text(), SVG)

    def test_no_overwrite_on_render_failure(self):
        """При ошибке рендеринга прежние файлы остаются целыми."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "diagram.svg"
            target.write_text("old")
            with patch("src.visualization.render_svg",
                       side_effect=VisualizationError("failed")):
                with self.assertRaises(VisualizationError):
                    save_visualization({"A": ()}, target)
            self.assertEqual(target.read_text(), "old")

    def test_write_error(self):
        """Ошибка файловой системы превращается в ошибку визуализации."""
        with patch("src.visualization.render_svg", return_value=SVG):
            with patch("pathlib.Path.write_text",
                       side_effect=OSError("denied")):
                with self.assertRaisesRegex(VisualizationError, "сохранить"):
                    save_visualization({"A": ()}, Path("graph.svg"))

    @unittest.skipUnless(os.environ.get("PLANTUML_JAR") or
                         shutil.which("plantuml"), "Нужен локальный PlantUML")
    def test_real_plantuml_cycle(self):
        """Реальный PlantUML сохраняет обе связи циклического графа в SVG."""
        graph = {"A": ("B",), "B": ("A",)}
        svg = render_svg(plantuml_source(graph))
        self.assertIn('id="entity_n0"', svg)
        self.assertIn('id="entity_n1"', svg)
        self.assertIn('id="link_n0_n1"', svg)
        self.assertIn('id="link_n1_n0"', svg)

    def test_cli_output_path(self):
        """Выходной путь разрешается относительно каталога конфигурации."""
        settings = Settings("A", "repo.json", True, "1.0.0", "result.svg")
        output = io.StringIO()
        with patch("src.main.load_settings", return_value=settings):
            with patch("src.main.build_graph", return_value={"A": ()}):
                with patch("src.main.save_visualization",
                           return_value=("x.puml", "x.svg")) as save:
                    with contextlib.redirect_stdout(output):
                        code = main(["--config", "examples/test.ini",
                                     "--visualize"])
        self.assertEqual(code, 0)
        self.assertEqual(save.call_args.args[1], Path("examples/result.svg"))
        self.assertIn("SVG: x.svg", output.getvalue())

    def test_cli_error(self):
        """Ошибка визуализации возвращает код 2 без traceback."""
        errors = io.StringIO()
        with patch("src.main.build_graph", return_value={"A": ()}):
            with patch("src.main.save_visualization",
                       side_effect=VisualizationError("failed")):
                with contextlib.redirect_stderr(errors):
                    code = main(["--config", "examples/test.ini",
                                 "--visualize"])
        self.assertEqual(code, 2)
        self.assertIn("Ошибка визуализации", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_mutually_exclusive_modes(self):
        """Режимы визуализации и порядка загрузки не запускаются совместно."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["--config", "examples/test.ini", "--visualize",
                      "--load-order"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
