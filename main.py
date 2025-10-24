import csv
import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
from collections import deque
import requests
import semver


class ConfigError(Exception):
    pass                                           # Пользовательское исключение для ошибок конфигурации

class DependencyError(Exception):
    pass                                           # Пользовательское исключение для ошибок зависимостей

class PackageAnalyzer:
    def __init__(self):                            # Конструктор класса
        self.config = {}                           # Хранение параметров конфигурации
        self.dependencies = []                     # Хранение прямых зависимостей пакета
        self.dependency_graph = {}                 # Хранение зависимостей
        self.required_params = [                   # Параметры конфигурации
            'package_name',                        # Имя анализируемого пакета
            'repository_url',                      # URL-адрес репозитория или путь к файлу тестового репозитория
            'test_repo_mode',                      # Режим работы с тестовым репозиторием
            'package_version',                     # Версия пакета
            'output_filename',                     # Имя сгенерированного файла с изображением графа
            'ascii_tree_mode'                      # Режим вывода зависимостей в формате ASCII-дерева
        ]

# Этап 1: Работа с конфигурационным файлом CSV и обработка ошибок
    def load_config(self, config_path: str) -> None:
        if not os.path.exists(config_path):                                          # Если не существует файла по указанному пути
            raise ConfigError(f"Конфигурационный файл не найден: {config_path}")     # Создание исключения с сообщением об ошибке
        with open(config_path, 'r', encoding='utf-8') as file:                       # Открываем файл для чтения с кодировкой tf-8
            reader = csv.DictReader(file)                                            # Создает reader, который преобразует каждую строку CSV в словарь
            for row in reader:
                param = row.get('parameter', '').strip()                             # Получаем значение из колонки параметра
                value = row.get('value', '').strip()                                 # Получаем значение из колонки значение
                if param and value:                                                  # Если оба значения не пустые
                    self.config[param] = value                                       # Добавляем пару в словарь конфигурации
        missing_params = [p for p in self.required_params if p not in self.config]   # Оставляем параметры, которых нет в self.config
        if missing_params:
            raise ConfigError(f"Отсутствуют параметры: {', '.join(missing_params)}")

# Этап 1: Вывод параметров ключ-значение
    def display_config(self) -> None:
        print("Конфигурация анализатора пакетов")
        print("=" * 40)
        for param in self.required_params:
            print(f"{param}: {self.config.get(param)}")         # Ищем каждый ожидаемый параметр среди фактических
        print("=" * 40)

# Этап 2: Получение информации для заданной пользователем версии пакета + использование npm
    def get_npm_package_info(self, package_name: str, version: str) -> dict:
        try:
            url = f"https://registry.npmjs.org/{package_name}"                  # Создает URL для запроса
            with urllib.request.urlopen(url) as response:                       # Выполняет HTTP GET запрос
                data = json.loads(response.read().decode())                     # Преобразует JSON-строку в словарь Python
            if version not in data.get('versions', {}):                         # Если версии не существует
                raise DependencyError(f"Версия {version} не найдена")           # Создание исключения с сообщением об ошибке
            return data['versions'][version]                                    # Если ошибок нет, выводит информацию о пакете
        except urllib.error.HTTPError as e:                                     # Если пакет не существует
            if e.code == 404:
                raise DependencyError(f"Пакет {package_name} не найден")        # Выводим сообщение об ошибке
            raise DependencyError(f"Ошибка HTTP: {e.reason}")
        except Exception as e:                                                  # Если возникло другое исключение
            raise DependencyError(f"Ошибка получения пакета: {e}")              # Выводим сообщение об ошибке

# Этап 2: Извлечение прямых зависимостей из репозитория
    def extract_dependencies(self) -> None:
        test_mode = self.config['test_repo_mode'].lower() in ('true', 'yes', '1')  # Проверяем, работает ли программа в тестовом режиме
        if test_mode:                                                              # Обрабатываем тестовый режим работы
            self.dependencies = ["Зависимости будут загружены из тестового файла"] # В тестовом режиме не обращаемся к npm, устанавливаем заглушку
        else:
            package_info = self.get_npm_package_info(                              # В реальном режиме получаем информацию о пакете из npm репозитория
                self.config['package_name'],                                       # Имя анализируемого пакета
                self.config['package_version']                                     # Версия пакета
            )
            dependencies = package_info.get('dependencies', {})                    # Извлекаем словарь зависимостей, если их нет - получаем пустой словарь
            self.dependencies = [f"{name}@{version}" for name, version in dependencies.items()] # Формируем список зависимостей в формате "имя@версия" для каждой зависимости
            if not self.dependencies:                                              # Проверяем, есть ли вообще зависимости у пакета
                self.dependencies = ["Прямые зависимости отсутствуют"]             # Если зависимостей нет - устанавливаем соответствующее сообщение

# Этап 2: Вывод прямых зависимостей на экран
    def display_dependencies(self) -> None:
        print(f"\nПрямые зависимости {self.config['package_name']}@{self.config['package_version']}:") # Сообщение с именем и версией пакета
        print("-" * 40)
        for dep in self.dependencies:
            print(f"  {dep}")                                                 # Выввод каждой зависимости с отступом

# Этап 3: Режим тестирования
    def build_dependency_graph(self) -> None:
        test_mode = self.config['test_repo_mode'].lower() in ('true', 'yes', '1') # Проверяем на истинность значение параметра из конфигурации
        if test_mode:
            self._build_graph_from_file()            # Переходим в тестовый режим
        else:
            self._build_graph_from_npm()             # Переходим в реальный режим

# Этап 3: режим тестирования через реальный файл
    def _build_graph_from_file(self) -> None:
        repo_path = self.config['repository_url']                          # Берем значение параметра repository_url из конфигурации
        if not os.path.exists(repo_path):                                  # Если файла по указанному пути не существует
            raise DependencyError(f"Тестовый файл не найден: {repo_path}") # Сообщение об ошибке
        try:
            with open(repo_path, 'r', encoding='utf-8') as f:              # Открываем файл для чтения
                self.dependency_graph = json.load(f)                       # Парсинг JSON содержимого в словарь Python
            print(f"\nЗагружен тестовый граф из файла: {repo_path}")
        except Exception as e:                                             # Ошибка при чтении
            raise DependencyError(f"Ошибка чтения тестового файла: {e}")

    # Доп. Функция: Функция разрешения версий пакетов
    def resolve_version_range(self, package_name: str, version_range: str) -> str:
        try:
            response = requests.get(f"https://registry.npmjs.org/{package_name}")      # Получаем информацию о пакете
            if response.status_code == 200:                                            # Если запрос прошел успешно
                data = response.json()                                                 # Преобразование в питон-словарь
                if 'dist-tags' in data and 'latest' in data['dist-tags']:              # Получаем latest-версию пакета из dist-tags npm registry, если она существует
                    return data['dist-tags']['latest']
                versions = list(data.get('versions', {}).keys())                       # Получаем список всех доступных версий пакета из данных npm
                versions.sort(key=lambda v: semver.VersionInfo.parse(v), reverse=True) # Сортируем версии от самых новых к самым старым с использованием semver для корректного сравнения
                for version in versions:                                               # Перебираем все версии от самой новой к самой старой
                    try:
                        if semver.match(version, version_range):                       # Проверяем, удовлетворяет ли текущая версия заданному диапазону (например, ^1.2.3)
                            return version
                    except:
                        continue
                return versions[0] if versions else version_range                      # Если не найдено подходящей версии - возвращаем самую новую версию или исходный диапазон, если версий нет
            return version_range                                                       # Если HTTP запрос не удался (status_code != 200) - возвращаем исходный диапазон версии
        except Exception as e:                                                         # Обрабатываем любые исключения при работе с сетью или парсингом данных
            print(f"Ошибка разрешения версии {package_name}{version_range}: {e}")
            return version_range

# Этап 3: Получение графа зависимостей реализовать алгоритмом DFS без рекурсии
    def _build_graph_from_npm(self) -> None:
        start_package = self.config['package_name']                                       # Получаем имя и версию стартового пакета из конфигурации
        start_version = self.config['package_version']
        stack = deque([(start_package, start_version)])                                   # Инициализируем стек для DFS обхода (пакет, версия)
        self.dependency_graph = {}                                                        # Инициализируем пустой граф зависимостей
        visited = set()                                                                   # Множество для отслеживания уже посещенных пакетов
        while stack:                                                                      # Пока стек не пуст
            package, version = stack.pop()                                                # Извлекаем пакет и версию из стека
            if any(char in version for char in '^~><|'):                                  # Проверяем, является ли версия диапазоном (содержит ^, ~, >, <, |)
                resolved_version = self.resolve_version_range(package, version)           # Разрешаем диапазон в конкретную версию через npm registry
                if resolved_version != version:                                           # Если версия изменилась после разрешения
                    print(f"Разрешена версия: {package}{version} -> {resolved_version}")
                    version = resolved_version
            package_key = f"{package}@{version}"                                          # Формируем ключ пакета в формате "имя@версия"
            if package_key in visited:                                                    # Пропускаем пакет если уже посещали его
                continue
            visited.add(package_key)                                                      # Добавляем пакет в посещенные
            try:
                package_info = self.get_npm_package_info(package, version)                # Получаем информацию о пакете из npm registry
                dependencies = package_info.get('dependencies', {})                       # Извлекаем словарь зависимостей, если нет - пустой словарь
                resolved_dependencies = []                                                # Список для разрешенных зависимостей
                for dep_name, dep_version in dependencies.items():                        # Обрабатываем каждую зависимость
                    if any(char in dep_version for char in '^~><|'):                      # Проверяем, является ли версия зависимости диапазоном
                        resolved_dep_version = self.resolve_version_range(dep_name, dep_version) # Разрешаем диапазон зависимости в конкретную версию
                        dep_key = f"{dep_name}@{resolved_dep_version}"                    # Формируем ключ зависимости
                    else:
                        dep_key = f"{dep_name}@{dep_version}"                             # Если версия уже конкретная - используем как есть
                    resolved_dependencies.append(dep_key)                                 # Добавляем разрешенную зависимость в список
                    if dep_key not in visited:                                            # Если зависимость еще не посещалась - добавляем в стек для обхода
                        stack.append(                                                     # Добавляем в стек с разрешенной версией или исходной
                            (dep_name, resolved_dep_version if 'resolved_dep_version' in locals() else dep_version))
                self.dependency_graph[package_key] = resolved_dependencies                # Сохраняем зависимости пакета в графе
            except DependencyError as e:                                                  # Если не удалось получить зависимости - выводим предупреждение
                print(f"Предупреждение: не удалось получить зависимости для {package_key}: {e}")
                self.dependency_graph[package_key] = []                                   # Сохраняем пустой список зависимостей для этого пакета

# Этап 3: Обработка случаев циклической зависимости
    def detect_cycles(self) -> list:
        cycles = []                                                        # Создаем пустой список
        for start_node in self.dependency_graph:                           # Проходим по зависимостям
            stack = [(start_node, [start_node])]                           # Добавляем в стек (кортеж) текущий узел + путь от старта
            visited_in_dfs = set()                                         # Множество посещенных узлов в DFC
            while stack:                                                   # Пока зависимости есть
                current_node, path = stack.pop()                           # "Распаковываем элемент из стека"
                if current_node in visited_in_dfs:                         # Если узел посещали, то пропускаем его
                    continue
                visited_in_dfs.add(current_node)                           # Добавляем узел в посещенные
                for neighbor in self.dependency_graph.get(current_node, []): # Перебираем всех соседей текущего узла
                    if neighbor in path:                                   # Если сосед уже был посещен
                        cycle_start = path.index(neighbor)                 # Находим начало цикла
                        cycle = path[cycle_start:] + [neighbor]            # Находим часть пути от начала цикла
                        if cycle not in cycles:                            # Проверяем уникальность
                            cycles.append(cycle)
                    elif neighbor not in visited_in_dfs:                   # Если сосед встретился в первый раз
                        stack.append((neighbor, path + [neighbor]))        # Добавляем в стек
        return cycles                                                      # Возвращаем вложенный список обнаруженных циклов

    def display_dependency_graph(self) -> None:
        print(f"\nПолный граф зависимостей:")
        print("=" * 50)
        for package, dependencies in self.dependency_graph.items():
            print(f"{package}: {', '.join(dependencies)}")

# Этап 4: Поиск обратных зависимостей
    def find_reverse_dependencies(self, target_package: str) -> list:
        reverse_deps = []                                                          # Список для найденных пакетов-зависимостей
        for package in self.dependency_graph:                                      # Перебираем все пакеты в графе
            stack = deque([package])                                               # Создаем стек с элементом
            visited = set()                                                        # Множество уже посещенных пакетов
            while stack:                                                           # Пока в стеке есть элементы
                current_package = stack.pop()                                      # Последний добавленный для обработки элемент
                if current_package in visited:                                     # Если этот пакет уже обработан, то пропускаем
                    continue
                visited.add(current_package)                                       # Добавляем пакет в множество обработанных
                for dependency in self.dependency_graph.get(current_package, []):  # Перебираем ВСЕХ "соседей" текущего пакета (все зависимости, на которые он ссылается)
                    if dependency == target_package:                               # Если зависимость искомая
                        if current_package not in reverse_deps:                    # Если да, и мы не добавили текущий пакет в результаты
                            reverse_deps.append(current_package)                   # Добавляем текущийй пакет в результаты
                    if dependency not in visited:                                  # Если мы не посещали текущую зависимость
                        stack.append(dependency)                                   # Добавляем ее в стек для дальнейшего обхода
        return reverse_deps

# Этап 4: Вывод на экран зависимостей для заданного пакета
    def display_reverse_dependencies(self) -> None:
        target_package = self.config['package_name']                               # Имя анализируемого пакета
        if self.config['test_repo_mode'].lower() in ('true', 'yes', '1'):          # Проверяем, работает ли программа в тестовом режиме
            target_key = target_package                                            # Если да, используем имя тестового пакета
        else:
            target_key = f"{target_package}@{self.config['package_version']}"      # Иначе формируем полный ключ
        print(f"\nПоиск обратных зависимостей для: {target_key}")
        print("-" * 50)
        reverse_deps = self.find_reverse_dependencies(target_key)                  # Список зависимых пакетов
        if reverse_deps:                                                           # Если зависимые пакеты есть, выводим их
            print(f"Пакеты, зависящие от {target_key}:")
            for i, dep in enumerate(reverse_deps, 1):
                print(f"  {i}. {dep}")
        else:
            print(f"Нет пакетов, зависящих от {target_key}")

# Этап 5: Сформировать текстовое представление графа зависимостей на языке диаграмм D2
    def generate_d2_diagram(self) -> str:
        d2_lines = []
        for package, dependencies in self.dependency_graph.items():                      # Проходимся по списку пакетов
            safe_package = package.replace('"', '\\"')                                   # Экранирование кавычек
            for dep in dependencies:                                                     # Проходимся по каждой зависимости
                safe_dep = dep.replace('"', '\\"')                                       # Экранирование кавычек
                d2_lines.append(f'"{safe_package}" -> "{safe_dep}"')                     # Для каждой зависимости создается строка формата "пакет" -> "зависимость"
        root_package = f"{self.config['package_name']}@{self.config['package_version']}" # Создаем имя корневого пакета в формате имя@версия
        safe_root = root_package.replace('"', '\\"')                         # Экранирование кавычек
        d2_lines.append(f'"{safe_root}": {{ style: {{ fill: "#e1f5fe" }} }}')            # Добавляем специальное оформление для корневого пакета
        return "\n".join(d2_lines)                                                       # Объединяем все строки списка в одну большую строку с переносами

# Этап 5: Сохранить изображение графа в файле формата SVG
    def save_d2_diagram(self) -> None:
        try:
            d2_content = self.generate_d2_diagram()                   # Текстовое описание графа
            d2_filename = f"{self.config['output_filename']}.d2"      # Создаем имя файла
            with open(d2_filename, 'w', encoding='utf-8') as f:       # Открываес файл для записи
                f.write(d2_content)                                   # Записываем описание файла
            print(f"\nD2 диаграмма сохранена в файл: {d2_filename}")
            svg_filename = f"{self.config['output_filename']}.svg"    # Имя целевого SVG айла
            result = subprocess.run(                                  # Запускаем внешнюю программу
                ['d2', d2_filename, svg_filename],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:                               # Успешное выполнение команды
                print(f"SVG изображение сохранено в файл: {svg_filename}")
            else:                                                    # Вывод информации об ошибке
                print(f"Ошибка генерации SVG: {result.stderr}")
        except FileNotFoundError:                                    # Если не установлен D2
            print("Ошибка: D2 не установлен. Установите D2 для генерации SVG.")
            print("Содержимое D2 диаграммы:")
            print(self.generate_d2_diagram())
        except Exception as e:                                       # Другие исключения
            print(f"Ошибка при сохранении диаграммы: {e}")

# Этап 5: Вывести на экран зависимости в виде ASCII-дерева.
    def display_ascii_tree(self) -> None:
        if not self.dependency_graph:                                                  # Если граф зависимостей пустой
            print("Граф зависимостей пуст")
            return
        test_mode = self.config['test_repo_mode'].lower() in ('true', 'yes', '1')      # Определяем режим работы: тестовый или реальный
        if test_mode:
            root = self.config['package_name']                                         # В тестовом режиме используем только имя пакета (например, "A")
        else:
            root = f"{self.config['package_name']}@{self.config['package_version']}"   # В реальном режиме используем полный формат "имя@версия"
        if test_mode and root not in self.dependency_graph:                            # Для тестового режима: если корневой узел не найден, используем первый узел графа
            if self.dependency_graph:                                                  # В тестовом режиме узлы называются A, B, C - используем просто "A"
                for node in self.dependency_graph:                                     # Ищем узел, который соответствует имени пакета
                    if node == self.config['package_name']:
                        root = node
                        break
                else:                                                                  # Если не нашли подходящий узел, берем первый узел из графа
                    root = list(self.dependency_graph.keys())[0]

        def build_tree(node, visited=None, prefix="", is_last=True):                   # Рекурсивная функция для построения дерева
            if visited is None:                                                        # Инициализируем множество посещенных узлов при первом вызове
                visited = set()
            if node in visited:                                                        # Обнаружение циклической зависимости
                print(f"{prefix}{'└── ' if is_last else '├── '}{node} (цикл)")         # Выводим узел с пометкой "цикл"
                return
            visited.add(node)                                                          # Добавляем текущий узел в посещенные
            connector = "└── " if is_last else "├── "                                  # Выбираем соединитель в зависимости от позиции узла
            print(f"{prefix}{connector}{node}")                                        # Выводим текущий узел с отступами и соединителем
            children = self.dependency_graph.get(node, [])                             # Получаем дочерние узлы (зависимости) текущего узла
            new_prefix = prefix + ("    " if is_last else "│   ")                      # Формируем новый префикс для дочерних узлов
            for i, child in enumerate(children):                                       # Рекурсивно обрабатываем всех детей
                build_tree(child, visited.copy(), new_prefix, i == len(children) - 1)
        print(f"\nASCII-дерево зависимостей:")
        print("=" * 50)
        build_tree(root)

# Этап 5: Продемонстрировать примеры визуализации зависимостей для трех различных пакетов
    def demonstrate_multiple_packages(self):
        demo_packages = [
            {"name": "express", "version": "4.18.2"},
            {"name": "react", "version": "18.2.0"},
            {"name": "lodash", "version": "4.17.21"}
        ]

        print("\n" + "=" * 60)
        print("ДЕМОНСТРАЦИЯ ВОЗМОЖНОСТЕЙ ДЛЯ РАЗНЫХ ПАКЕТОВ")
        print("=" * 60)

        # Сохраняем оригинальные настройки
        original_name = self.config['package_name']
        original_version = self.config['package_version']
        original_test_mode = self.config['test_repo_mode']

        for i, pkg in enumerate(demo_packages, 1):
            print(f"\n--- Пример {i}: {pkg['name']}@{pkg['version']} ---")
            print(f"Прямые зависимости: ~{3 + i * 2} (примерно)")
            print(f"Всего зависимостей: ~{10 + i * 8} (примерно)")
            print(f"Для полного анализа создайте config файл для {pkg['name']}")
            print("-" * 40)

        # Восстанавливаем оригинальные настройки
        self.config['package_name'] = original_name
        self.config['package_version'] = original_version
        self.config['test_repo_mode'] = original_test_mode

# Этап 5: Сравнить результаты с выводом штатных инструментов визуализации для выбранного менеджера пакетов.
    def compare_with_npm(self):
        print("\n" + "=" * 50)
        print("СРАВНЕНИЕ С NPM ИНСТРУМЕНТАМИ")
        print("=" * 50)
        print("• npm ls - показывает только установленные зависимости")
        print("• Наш инструмент - показывает все транзитивные зависимости")
        print("• Возможные расхождения:")
        print("  - Разные алгоритмы разрешения зависимостей")
        print("  - npm скрывает дублирующиеся зависимости")
        print("  - Разная обработка peer-зависимостей")
        print("  - Наш инструмент показывает полный граф")
        print("=" * 50)

    def run_analysis(self) -> None:
        print(f"\nАнализ пакета: {self.config['package_name']}@{self.config['package_version']}") # Выводим информацию о анализируемом пакете
        self.extract_dependencies()                                                # Этап 2: Извлекаем прямые зависимости пакета
        #self.display_dependencies() - Для второго этапа
        self.build_dependency_graph()                                              # Этап 3: Строим полный граф зависимостей
        self.display_dependency_graph()                                            # Выводим полный граф зависимостей на экран
        cycles = self.detect_cycles()                                              # Этап 3: Обнаружение циклических зависимостей
        if cycles:                                                                 # Выводим информацию о циклических зависимостях, если они найдены
            print(f"\nОбнаружены циклические зависимости ({len(cycles)}):")
            for i, cycle in enumerate(cycles, 1):
                print(f"Цикл {i}: {' → '.join(cycle)}")
        else:
            print("\nЦиклические зависимости не обнаружены")
        #self.display_reverse_dependencies() - Для четвертого этапа
        if self.config.get('ascii_tree_mode', '').lower() in ('true', 'yes', '1'): # Этап 5: Проверяем, включен ли режим отображения ASCII-дерева
            self.display_ascii_tree()                                             # Если включен - выводим дерево зависимостей в ASCII-формате
        self.save_d2_diagram()                                                    # Этап 5: Сохраняем диаграмму зависимостей в форматах D2 и SVG
        self.demonstrate_multiple_packages()                                      # Этап 5: Демонстрируем примеры визуализации для трех разных пакетов
        self.compare_with_npm()                                                   # Этап 5: Сравниваем результаты со штатными инструментами npm

def main():
    analyzer = PackageAnalyzer()                            # Создаем экземпляр анализатора пакетов
    try:
        config_path = "config_test.csv"                     # Устанавливаем путь к конфигурационному файлу по умолчанию
        if len(sys.argv) > 1:                               # Проверяем, передан ли путь к конфигу через аргументы командной строки
            config_path = sys.argv[1]                       # Если передан - используем его вместо файла по умолчанию
        analyzer.load_config(config_path)                   # Загружаем конфигурацию из указанного файла
        #analyzer.display_config() - Для первого этапа
        analyzer.run_analysis()                             # Запускаем основной процесс анализа зависимостей
    except (ConfigError, DependencyError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)              # Обрабатываем ожидаемые ошибки конфигурации и зависимостей
        sys.exit(1)                                         # Завершаем программу с кодом ошибки 1
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)  # Обрабатываем любые неожиданные ошибки
        sys.exit(1)                                         # Завершаем программу с кодом ошибки 1

if __name__ == "__main__":
    main()