"""Разбор SemVer и выбор версии без сторонних библиотек."""

import operator
import re


PART_COUNT = 3
MINOR = 1
EMPTY_CORE = (0, 0, 0)
STABLE = ((2, ""),)
COMPARISONS = {
    "=": operator.eq, ">": operator.gt, ">=": operator.ge,
    "<": operator.lt, "<=": operator.le,
}
FULL_VERSION = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([\da-zA-Z-]+(?:\.[\da-zA-Z-]+)*))?"
    r"(?:\+[\da-zA-Z-]+(?:\.[\da-zA-Z-]+)*)?"
)
PARTIAL_VERSION = re.compile(
    r"v?([\dxX*]+(?:\.[\dxX*]+){0,2})"
    r"(-[\da-zA-Z.-]+)?(?:\+([\da-zA-Z.-]+))?"
)


class VersionError(ValueError):
    """Неверная версия или неподдерживаемое ограничение версий."""


def version_key(version):
    """Получить ключ SemVer; build не влияет на порядок версий."""
    match = FULL_VERSION.fullmatch(version)
    if not match:
        raise VersionError(f"Некорректная версия: {version}")
    core = tuple(int(value) for value in match.groups()[:PART_COUNT])
    prerelease = match.group(4)
    if prerelease is None:
        return core, STABLE
    identifiers = []
    for part in prerelease.split("."):
        if part.isdigit():
            if part != str(int(part)):
                raise VersionError(f"Ведущие нули в версии: {version}")
            identifiers.append((0, int(part)))
        else:
            identifiers.append((1, part))
    return core, tuple(identifiers)


def partial_version(text):
    """Разобрать полную, неполную версию или шаблон x/*."""
    match = PARTIAL_VERSION.fullmatch(text)
    if not match:
        raise VersionError(f"Неподдерживаемое ограничение: {text}")
    parts = match.group(1).split(".")
    numbers = []
    wildcard = False
    for part in parts:
        if part.lower() in {"x", "*"}:
            wildcard = True
        elif wildcard:
            raise VersionError(f"Число после шаблона: {text}")
        else:
            numbers.append(int(part))
    core = tuple(numbers + [0] * (PART_COUNT - len(numbers)))
    suffix = match.group(2) or ""
    if suffix and len(numbers) != PART_COUNT:
        raise VersionError(f"Неполная prerelease-версия: {text}")
    key = version_key(".".join(map(str, core)) + suffix)
    return key, len(numbers)


def next_core(core, index):
    """Увеличить компонент версии и обнулить младшие компоненты."""
    result = list(core)
    result[index] += 1
    result[index + 1:] = [0] * (PART_COUNT - index - 1)
    return tuple(result), STABLE


def caret_upper(core, count):
    """Определить верхнюю границу ^ с учётом нулевых компонентов."""
    for index in range(count):
        if core[index]:
            return next_core(core, index)
    return next_core(core, count - 1)


def partial_comparators(op, key, count):
    """Преобразовать неполную версию в обычные сравнения."""
    if not count:
        if op in {"<", ">"}:
            return [("<", (EMPTY_CORE, STABLE))]
        return []
    upper = next_core(key[0], count - 1)
    expansions = {
        "=": [(">=", key), ("<", upper)],
        ">=": [(">=", key)], "<": [("<", key)],
        ">": [(">=", upper)], "<=": [("<", upper)],
    }
    return expansions[op]


def token_comparators(token):
    """Преобразовать точную версию, ^, ~ или компаратор в границы."""
    match = re.fullmatch(r"(<=|>=|<|>|=|\^|~)?(.+)", token)
    if not match:
        raise VersionError(f"Неверное ограничение: {token}")
    op = match.group(1) or "="
    key, count = partial_version(match.group(2))
    if op in {"^", "~"}:
        if not count:
            return []
        index = min(count - 1, MINOR)
        upper = next_core(key[0], index)
        if op == "^":
            upper = caret_upper(key[0], count)
        return [(">=", key), ("<", upper)]
    if count != PART_COUNT:
        return partial_comparators(op, key, count)
    return [(op, key)]


def compile_range(expression):
    """Разобрать альтернативы ||, пересечения и диапазоны через дефис."""
    groups = []
    for group in expression.split("||"):
        group = re.sub(r"([^\s]+)\s+-\s+([^\s]+)", r">=\1 <=\2", group)
        group = re.sub(r"(<=|>=|<|>|=|\^|~)\s+", r"\1", group)
        tokens = group.split() or ["*"]
        comparisons = []
        prerelease_cores = set()
        for token in tokens:
            bounds = token_comparators(token)
            comparisons.extend(bounds)
            for _, key in bounds:
                if key[1] != STABLE:
                    prerelease_cores.add(key[0])
        groups.append((comparisons, prerelease_cores))
    return groups


def matches_group(key, group):
    """Проверить пересечение, исключая не запрошенные prerelease-версии."""
    comparisons, prerelease_cores = group
    if key[1] != STABLE and key[0] not in prerelease_cores:
        return False
    return all(COMPARISONS[op](key, bound) for op, bound in comparisons)


def select_version(versions, expression, tags=None):
    """Выбрать наибольшую подходящую версию или dist-tag npm."""
    tags = tags or {}
    if expression in tags:
        expression = tags[expression]
    if not isinstance(expression, str):
        raise VersionError("Ограничение или dist-tag должно быть строкой")
    groups = compile_range(expression)
    candidates = []
    for version in versions:
        try:
            key = version_key(version)
        except VersionError:
            continue
        if any(matches_group(key, group) for group in groups):
            candidates.append((key, version))
    if not candidates:
        raise VersionError(f"Нет версии для ограничения {expression}")
    return max(candidates)[1]
