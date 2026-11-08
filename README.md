# Dependency Graph

## Общее описание

Практическая работа по дисциплине «Конфигурационное управление».
ИКБО-32-25, вариант 13. Язык реализации — Python.

Программа читает конфигурационный файл INI и строит граф зависимостей
заданной версии npm-пакета с учётом транзитивных зависимостей.
Режим `--load-order` выводит порядок загрузки пакетов.
Режим `--visualize` формирует PlantUML и сохраняет SVG.
Данные получаются из npm Registry средствами
стандартной библиотеки Python, без использования менеджеров пакетов
и сторонних библиотек для получения зависимостей.

## Функции и настройки

Путь к конфигурации задаётся обязательной опцией `--config`.
INI-файл в кодировке UTF-8 должен содержать секцию `[app]` и пять ключей.
Все ключи обязательны; пустые значения и неизвестные ключи отклоняются.

| Ключ | Назначение и допустимые значения |
| --- | --- |
| `package` | Имя npm-пакета: `express`, `@types/node`. В тестовом режиме — заглавные латинские буквы, например `A`. |
| `repository` | HTTP(S) URL без пароля, query и fragment; в тестовом режиме — путь к существующему читаемому файлу. |
| `test_mode` | Логическое значение: `true/false`, `yes/no`, `on/off`, `1/0`, без учёта регистра. |
| `version` | Конкретная SemVer-версия: `4.18.2`, `1.0.0-beta.1`; диапазоны и `latest` запрещены. |
| `output` | Путь SVG, например `graph.svg`; родительский каталог должен существовать. |

Относительные пути отсчитываются от каталога INI-файла.
Таймаут HTTP-запроса — 15 секунд. Анализируется поле `dependencies`.
Граф строится алгоритмом BFS без рекурсии, через очередь.
Каждый узел обрабатывается один раз; циклические связи сохраняются.
По умолчанию выводятся списки смежности в порядке обхода BFS.
Опция `--load-order` переключает вывод на порядок загрузки:
каждая зависимость предшествует использующим её пакетам, корень идёт последним.
Для графа без циклов применяется топологическая сортировка через очередь.
Пакеты, между которыми нет зависимости, могут иметь несколько допустимых
порядков; программа выбирает их по порядку обнаружения в BFS-графе.
При цикле или самоссылке строгий порядок невозможен: выводится ошибка,
код завершения — 2. Обычный режим по-прежнему показывает циклические связи.
Опция `--visualize` сохраняет изображение SVG по пути `output` из INI,
а исходник PlantUML — рядом с тем же именем и расширением `.puml`.
Направление стрелки: пакет → его зависимость. Циклы и самоссылки сохраняются.
Режимы `--load-order` и `--visualize` взаимоисключающие.
Рендеринг выполняется локально; сервер PlantUML не используется.
При ошибке рендеринга прежние файлы не перезаписываются.

Узел npm-графа имеет вид `имя@версия`. Для зависимости выбирается
наибольшая опубликованная версия, соответствующая её ограничению.
Поддерживаются точные версии, `^`, `~`, сравнения, неполные версии,
шаблоны `x`/`*`, диапазоны через дефис, альтернативы `||` и dist-tags.
Prerelease-версии выбираются при явном указании соответствующей версии
в ограничении. Источники `file:`, Git и npm-алиасы не поддерживаются;
при таком ограничении программа сообщает об ошибке.
Граф показывает зависимости выбранных версий пакетов; размещение пакетов
в `node_modules` и lock-файлы не моделируются.

В тестовом режиме используется локальный JSON-граф вида
`{"A": ["B", "C"], "B": [], "C": []}`. Имена пакетов состоят из заглавных
латинских букв. Каждый достижимый пакет должен быть описан в файле;
пустой список означает отсутствие зависимостей. Версии в формате не хранятся;
параметр `version` не влияет на выбор тестовых связей.
Тестовый файл читается один раз; обращения к сети не выполняются.

| Функция / класс | Назначение |
| --- | --- |
| `Settings` | Неизменяемый набор пяти проверенных параметров |
| `ConfigError` | Ошибка конфигурации, обрабатываемая CLI |
| `read_section(path)` | Чтение INI, проверка секций, ключей и пустых значений |
| `validate_package(package, test_mode)` | Проверка имени пакета |
| `validate_version(version)` | Проверка SemVer, включая prerelease |
| `local_path(value, base)` | Разрешение пути относительно INI |
| `validate_test_file(repository, base)` | Проверка читаемого файла |
| `validate_repository_url(repository)` | Проверка синтаксиса HTTP(S) URL |
| `validate_repository(repository, test_mode, base)` | Проверка URL или тестового файла |
| `validate_output(output, base)` | Проверка имени SVG и родительского каталога |
| `load_settings(path)` | Чтение и полная проверка настроек |
| `parse_arguments(argv)` | Разбор пути к конфигурации и режима CLI |
| `run_command(settings, arguments)` | Построение графа и выполнение выбранной операции |
| `main(argv=None)` | Запуск команды и обработка ошибок |
| `RegistryError` | Ошибка получения или разбора данных репозитория |
| `read_json(stream)` | Декодирование UTF-8 JSON-объекта |
| `fetch_json(url)` | Получение JSON по HTTP(S) и обработка сетевых ошибок |
| `fetch_catalogue(settings, package)` | Получение каталога версий npm-пакета |
| `fetch_metadata(settings)` | HTTP-запрос метаданных конкретной версии |
| `extract_dependencies(metadata, settings)` | Проверка ответа и извлечение dependencies |
| `read_test_graph(settings, base)` | Чтение JSON-файла тестового графа |
| `test_children(graph, package)` | Проверка и получение связей тестового узла |
| `read_test_dependencies(settings, base)` | Чтение прямых связей тестового пакета |
| `get_dependencies(settings, base)` | Выбор сетевого или тестового источника |
| `bfs_graph(root, children)` | Обход достижимых узлов очередью, сохранение всех связей |
| `NpmRepository` | Источник зависимостей npm с кешем метаданных |
| `NpmRepository.__init__(settings)` | Загрузка метаданных корневого пакета |
| `NpmRepository.resolve(package, constraint)` | Выбор версии зависимости и кеширование |
| `NpmRepository.children(node)` | Получение зависимостей узла имя@версия |
| `build_graph(settings, base)` | Построение npm-графа или тестового графа |
| `print_graph(graph)` | Вывод списков смежности в порядке BFS |
| `dependency_index(graph)` | Счётчики зависимостей и обратные связи |
| `loading_order(graph)` | Топологический порядок загрузки; ошибка при цикле |
| `print_loading_order(order)` | Нумерованный вывод порядка загрузки |
| `VisualizationError` | Ошибка рендеринга или сохранения файлов |
| `escape_label(label)` | Экранирование подписи узла PlantUML |
| `plantuml_source(graph)` | Формирование текста диаграммы PlantUML |
| `plantuml_command()` | Выбор локального PlantUML или Java с JAR |
| `validate_svg(svg)` | Проверка корректности XML и корневого SVG-элемента |
| `render_svg(source)` | Запуск PlantUML, таймаут 60 секунд, получение SVG |
| `save_visualization(graph, output)` | Запись исходника PlantUML и SVG |
| `VersionError` | Ошибка разбора версии или ограничения |
| `version_key(version)` | Ключ сравнения SemVer с учётом prerelease |
| `partial_version(text)` | Разбор неполной версии или шаблона |
| `next_core(core, index)` | Вычисление верхней границы диапазона |
| `caret_upper(core, count)` | Верхняя граница ограничения с ^ |
| `partial_comparators(op, key, count)` | Границы для неполных версий |
| `token_comparators(token)` | Границы отдельного ограничения |
| `compile_range(expression)` | Разбор альтернатив и пересечений ограничений |
| `matches_group(key, group)` | Проверка одного пересечения ограничений |
| `select_version(versions, expression, tags=None)` | Выбор подходящей версии или dist-tag |

## Сборка, запуск и тесты

Нужен Python 3.10 или новее. Сборка Python-кода и установка Python-пакетов
не требуются. Для `--visualize` дополнительно нужны PlantUML, Java и Graphviz.
Остальные режимы работают без PlantUML.
Команды выполняются из корня репозитория.

Установка PlantUML и Graphviz в Debian/Ubuntu:

```sh
sudo apt install plantuml graphviz
```

Вместо команды `plantuml` можно скачать JAR с официального сайта
[plantuml.com/download](https://plantuml.com/download) и задать путь к нему.
Java и Graphviz (`dot`) должны быть доступны в `PATH`.

Linux/macOS:

```sh
export PLANTUML_JAR=/absolute/path/to/plantuml.jar
```

PowerShell:

```powershell
$env:PLANTUML_JAR = "C:\tools\plantuml.jar"
```

Если `PLANTUML_JAR` не задан, используется команда `plantuml` из `PATH`.
JAR и установленные инструменты в git-репозиторий не добавляются.

Запуск:

```sh
python3 src/main.py --config examples/config.ini
```

Запуск через скрипт:

```sh
sh run.sh --config examples/config.ini
```

Вывод порядка загрузки:

```sh
sh run.sh --config examples/is-odd.ini --load-order
```

Визуализация:

```sh
sh run.sh --config examples/is-odd.ini --visualize
```

Будут сохранены `examples/is-odd.puml` и `examples/is-odd.svg`.
SVG можно открыть в браузере. Сгенерированные `.svg` и `.puml`
исключены из Git через `.gitignore`.

Запуск тестов:

```sh
python3 -m unittest discover -s tests -v
```

Автотесты не требуют сети. Проверка реального рендеринга выполняется,
если доступна команда `plantuml` или задана `PLANTUML_JAR`;
иначе этот интеграционный тест пропускается.

Справка:

```sh
python3 src/main.py --help
```

На Windows вместо `python3` можно использовать `python`.

## Примеры использования

Конфигурация `examples/config.ini`:

```ini
[app]
package = express
repository = https://registry.npmjs.org
test_mode = false
version = 4.18.2
output = graph.svg
```

Начало вывода команды `python3 src/main.py --config examples/config.ini`:

```text
Граф зависимостей (BFS):
express@4.18.2 -> accepts@1.3.8, array-flatten@1.1.1, ...
accepts@1.3.8 -> mime-types@2.1.35, negotiator@0.6.3
array-flatten@1.1.1 -> нет зависимостей
```

В примере список корневых связей сокращён; программа выводит все связи.
Для работы с npm Registry нужно подключение к сети.
Выбор версий зависит от опубликованного содержимого репозитория.

Тестовая цепочка:

```sh
python3 src/main.py --config examples/chain.ini
```

```text
Граф зависимостей (BFS):
A -> B
B -> C
C -> нет зависимостей
```

Ветвление с общей зависимостью:

```sh
python3 src/main.py --config examples/branch.ini
```

```text
Граф зависимостей (BFS):
A -> B, C
B -> D
C -> D
D -> нет зависимостей
```

Циклические зависимости:

```sh
python3 src/main.py --config examples/cycle.ini
```

```text
Граф зависимостей (BFS):
A -> B
B -> C
C -> A
```

Самоссылка:

```sh
python3 src/main.py --config examples/self.ini
```

```text
Граф зависимостей (BFS):
A -> A
```

Пакет без зависимостей:

```sh
python3 src/main.py --config examples/empty.ini
```

```text
Граф зависимостей (BFS):
A -> нет зависимостей
```

Порядок загрузки для цепочки:

```sh
python3 src/main.py --config examples/chain.ini --load-order
```

```text
Порядок загрузки зависимостей:
1. C
2. B
3. A
```

Ветвление с общей зависимостью:

```sh
python3 src/main.py --config examples/branch.ini --load-order
```

```text
Порядок загрузки зависимостей:
1. D
2. B
3. C
4. A
```

Для `examples/empty.ini` с той же опцией результат — `1. A`.
Для `examples/cycle.ini` и `examples/self.ini` программа возвращает код 2:

```sh
python3 src/main.py --config examples/cycle.ini --load-order
```

```text
Ошибка репозитория: Циклические зависимости: порядок загрузки невозможен; заблокированные пакеты: A, B, C
```

### Сравнение порядка загрузки с npm

Пример npm-пакета:

```sh
python3 src/main.py --config examples/is-odd.ini --load-order
```

```text
Порядок загрузки зависимостей:
1. is-number@6.0.0
2. is-odd@3.0.1
```

Для сравнения использованы npm 11.9.0 и Node.js 24.19.0.
Команды выполняются в отдельном пустом каталоге вне проекта:

```sh
mkdir npm-comparison
cd npm-comparison
npm install is-odd@3.0.1 --ignore-scripts --no-audit --no-fund --loglevel=silly
npm ls --all
```

`npm ls --all` показывает `is-odd@3.0.1`, зависящий от `is-number@6.0.0`.
В проверенном запуске журнал npm содержал:

```text
npm silly ADD node_modules/is-number
npm silly ADD node_modules/is-odd
```

Порядок записей `ADD` совпал с порядком программы: сначала `is-number`,
затем `is-odd`. При этом HTTP-запросы архивов в журнале завершились
в обратном порядке: сначала `is-odd-3.0.1.tgz`, затем `is-number-6.0.0.tgz`.
Это различие связано с параллельным скачиванием npm: физический порядок
сетевой загрузки не обязан быть топологическим. Программа рассчитывает
последовательность «зависимости перед зависимыми пакетами» и не скачивает архивы.
Порядок строк журнала npm может меняться между запусками из-за сети и кеша.
Само приложение получает данные стандартной библиотекой Python;
npm используется только для этого сравнения.

### Визуализация трёх npm-пакетов

После настройки локального PlantUML выполните:

```sh
python3 src/main.py --config examples/is-odd.ini --visualize
python3 src/main.py --config examples/is-even.ini --visualize
python3 src/main.py --config examples/is-number.ini --visualize
```

Результат — пары файлов `.puml` и `.svg` в `examples/` с именами пакетов.
Полученные графы:

```text
is-odd@3.0.1 -> is-number@6.0.0

is-even@1.0.0 -> is-odd@0.1.2 -> is-number@3.0.0 -> kind-of@3.2.2 -> is-buffer@1.1.6

is-number@7.0.0 — нет зависимостей
```

Пример исходника `is-odd.puml`:

```plantuml
@startuml
left to right direction
rectangle "is-odd@3.0.1" as n0
rectangle "is-number@6.0.0" as n1
n0 --> n1
@enduml
```

Для визуализации тестового цикла:

```sh
python3 src/main.py --config examples/cycle.ini --visualize
```

На диаграмме будут три узла и связи `A → B → C → A`.

### Сравнение визуализации с npm

Штатная команда npm для отображения дерева установленных зависимостей —
`npm ls --all`. Каждый пример устанавливается в отдельный пустой каталог
вне репозитория. Например, для `is-even`:

```sh
mkdir npm-is-even
cd npm-is-even
npm install is-even@1.0.0 --ignore-scripts --no-audit --no-fund
npm ls --all
```

Для двух других примеров повторите команды в отдельных каталогах,
заменив пакет на `is-odd@3.0.1` и `is-number@7.0.0`.
Сравнение выполнено с npm 11.9.0 и PlantUML 1.2025.2:

| Пакет | Узлов в SVG | Связей в SVG | Сравнение с npm ls --all |
| --- | --- | --- | --- |
| `is-odd@3.0.1` | 2 | 1 | Все имена, версии и связи совпали |
| `is-even@1.0.0` | 5 | 4 | Все имена, версии и связи совпали |
| `is-number@7.0.0` | 1 | 0 | Совпало отсутствие зависимостей |

Для этих примеров различий в составе графов нет. Формат представления
различается: npm выводит текстовое дерево, PlantUML — направленную диаграмму.
Для других пакетов возможны различия из-за lock-файлов, дедупликации npm,
peer/optional-зависимостей: программа анализирует поле `dependencies`
и самостоятельно выбирает максимальные подходящие версии.

Для демонстрации обработки ошибок замените соответствующее значение
в копии INI-файла и запустите программу с путём к этой копии.

| Параметр | Ошибочное значение | Причина |
| --- | --- | --- |
| `package` | `Bad Name` | Некорректное имя пакета |
| `repository` | `ftp://example.org` | Неподдерживаемая схема URL |
| `repository`, тестовый режим | `missing.json` | Несуществующий файл |
| `test_mode` | `maybe` | Не логическое значение |
| `version` | `latest` | Нужна конкретная версия SemVer |
| `output` | `graph.png` | Требуется расширение SVG |

Например, при `test_mode = maybe`:

```text
Ошибка конфигурации: test_mode: нужно true/false, yes/no, on/off, 1/0
```

При ошибке программа выводит сообщение в stderr и возвращает код 2.
При успешном выполнении возвращает код 0.

Ошибки отсутствующего PlantUML, Java, неправильного пути `PLANTUML_JAR`,
таймаут рендеринга и ошибки записи SVG также приводят к коду завершения 2
и сообщению `Ошибка визуализации: ...` в stderr.
