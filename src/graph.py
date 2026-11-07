"""Построение транзитивного графа зависимостей алгоритмом BFS."""

from collections import deque
from dataclasses import replace

if __package__:
    from .registry import (
        RegistryError, extract_dependencies, fetch_catalogue, fetch_metadata,
        read_test_graph, test_children,
    )
    from .versions import VersionError, select_version
else:
    from registry import (
        RegistryError, extract_dependencies, fetch_catalogue, fetch_metadata,
        read_test_graph, test_children,
    )
    from versions import VersionError, select_version


def bfs_graph(root, children):
    """Обойти граф очередью; сохранить циклы, каждый узел загрузить один раз."""
    queue = deque([root])
    discovered = {root}
    graph = {}
    while queue:
        node = queue.popleft()
        graph[node] = tuple(children(node))
        for dependency in graph[node]:
            if dependency not in discovered:
                discovered.add(dependency)
                queue.append(dependency)
    return graph


class NpmRepository:
    """Источник зависимостей с кешем каталогов и узлами имя@версия."""

    def __init__(self, settings):
        """Загрузить указанную пользователем точную версию корня."""
        self.settings = settings
        self.catalogues = {}
        self.metadata = {
            (settings.package, settings.version): fetch_metadata(settings),
        }

    def resolve(self, package, constraint):
        """Выбрать версию зависимости и сохранить её метаданные в кеше."""
        if package not in self.catalogues:
            self.catalogues[package] = fetch_catalogue(self.settings, package)
        data = self.catalogues[package]
        try:
            version = select_version(data["versions"], constraint,
                                     data.get("dist-tags"))
        except VersionError as error:
            raise RegistryError(f"{package}: {error}") from error
        metadata = data["versions"][version]
        if not isinstance(metadata, dict):
            raise RegistryError(f"Некорректные метаданные {package}@{version}")
        self.metadata[(package, version)] = metadata
        return f"{package}@{version}"

    def children(self, node):
        """Разрешить прямые зависимости выбранной версии узла."""
        package, version = node.rsplit("@", 1)
        settings = replace(self.settings, package=package, version=version)
        dependencies = extract_dependencies(
            self.metadata[(package, version)], settings,
        )
        return [self.resolve(name, constraint)
                for name, constraint in dependencies.items()]


def build_graph(settings, base):
    """Построить граф npm или тестового репозитория без рекурсии."""
    if settings.test_mode:
        source = read_test_graph(settings, base)
        return bfs_graph(settings.package,
                         lambda name: test_children(source, name))
    repository = NpmRepository(settings)
    root = f"{settings.package}@{settings.version}"
    return bfs_graph(root, repository.children)


def print_graph(graph):
    """Вывести списки смежности в порядке обхода BFS."""
    print("Граф зависимостей (BFS):")
    for node, dependencies in graph.items():
        print(f"{node} -> {', '.join(dependencies) or 'нет зависимостей'}")
