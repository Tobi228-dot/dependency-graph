"""Определение порядка загрузки: зависимости раньше зависимых пакетов."""

from collections import deque

if __package__:
    from .registry import RegistryError
else:
    from registry import RegistryError


def dependency_index(graph):
    """Построить счётчики зависимостей и обратные связи для сортировки."""
    pending = {}
    dependents = {node: [] for node in graph}
    for node, dependencies in graph.items():
        unique = tuple(dict.fromkeys(dependencies))
        pending[node] = len(unique)
        for dependency in unique:
            if dependency not in graph:
                raise RegistryError(f"В графе отсутствует узел {dependency}")
            dependents[dependency].append(node)
    return pending, dependents


def loading_order(graph):
    """Топологически отсортировать граф от листьев; отклонить циклы."""
    pending, dependents = dependency_index(graph)
    ready = deque(node for node, count in pending.items() if not count)
    order = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for dependent in dependents[node]:
            pending[dependent] -= 1
            if not pending[dependent]:
                ready.append(dependent)
    if len(order) != len(graph):
        blocked = ", ".join(node for node in graph if pending[node])
        raise RegistryError(
            "Циклические зависимости: порядок загрузки невозможен; "
            f"заблокированные пакеты: {blocked}"
        )
    return order


def print_loading_order(order):
    """Вывести пакеты в порядке загрузки, включая корневой пакет."""
    print("Порядок загрузки зависимостей:")
    for index, node in enumerate(order, start=1):
        print(f"{index}. {node}")
