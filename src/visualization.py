"""Формирование PlantUML и локальное сохранение графа в SVG."""

import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as element_tree


RENDER_TIMEOUT = 60
SVG_TAG = "{http://www.w3.org/2000/svg}svg"


class VisualizationError(ValueError):
    """Ошибка запуска PlantUML, формирования SVG или записи файлов."""


def escape_label(label):
    """Экранировать строку подписи узла PlantUML."""
    return (label.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r", "").replace("\n", "\\n"))


def plantuml_source(graph):
    """Сформировать PlantUML со всеми узлами, рёбрами и циклами."""
    aliases = {node: f"n{index}" for index, node in enumerate(graph)}
    lines = ["@startuml", "left to right direction"]
    for node, alias in aliases.items():
        lines.append(f'rectangle "{escape_label(node)}" as {alias}')
    for node, dependencies in graph.items():
        for dependency in dict.fromkeys(dependencies):
            if dependency not in aliases:
                raise VisualizationError(f"Нет узла {dependency} в графе")
            lines.append(f"{aliases[node]} --> {aliases[dependency]}")
    return "\n".join([*lines, "@enduml", ""])


def plantuml_command():
    """Выбрать локальный PlantUML или JAR из переменной PLANTUML_JAR."""
    jar = os.environ.get("PLANTUML_JAR")
    if jar:
        if not Path(jar).is_file():
            raise VisualizationError("PLANTUML_JAR: файл не найден")
        java = shutil.which("java")
        if not java:
            raise VisualizationError("Java не найдена в PATH")
        return [java, "-Djava.awt.headless=true", "-jar", jar]
    executable = shutil.which("plantuml")
    if not executable:
        raise VisualizationError(
            "Установите PlantUML или задайте PLANTUML_JAR (см. README)"
        )
    return [executable]


def validate_svg(svg):
    """Проверить, что результат рендеринга является SVG-документом."""
    try:
        root = element_tree.fromstring(svg)
    except element_tree.ParseError as error:
        raise VisualizationError("PlantUML вернул некорректный XML") from error
    if root.tag != SVG_TAG:
        raise VisualizationError("PlantUML не вернул SVG")


def render_svg(source):
    """Локально отрисовать PlantUML через subprocess без shell."""
    command = plantuml_command()
    command += ["-tsvg", "-pipe", "-charset", "UTF-8", "-failfast2"]
    try:
        result = subprocess.run(command, input=source, capture_output=True,
                                encoding="utf-8", timeout=RENDER_TIMEOUT,
                                check=False)
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        raise VisualizationError(f"Не удалось запустить PlantUML: {error}") \
            from error
    if result.returncode:
        raise VisualizationError(f"Ошибка PlantUML: {result.stderr.strip()}")
    validate_svg(result.stdout)
    return result.stdout


def save_visualization(graph, output):
    """Сохранить SVG и исходник PlantUML рядом с указанным файлом."""
    source = plantuml_source(graph)
    svg = render_svg(source)
    output = Path(output)
    source_path = output.with_suffix(".puml")
    try:
        source_path.write_text(source, encoding="utf-8")
        output.write_text(svg, encoding="utf-8")
    except OSError as error:
        raise VisualizationError(f"Не удалось сохранить граф: {error}") \
            from error
    return source_path, output
