import csv
import os
import sys
import json
import urllib.request
import urllib.error
from collections import deque

class ConfigError(Exception):
    pass

class DependencyError(Exception):
    pass

class PackageAnalyzer:
    def __init__(self):
        self.config = {}
        self.dependencies = []
        self.dependency_graph = {}
        self.required_params = [
            'package_name',
            'repository_url',
            'test_repo_mode',
            'package_version',
            'output_filename',
            'ascii_tree_mode'
        ]

    def load_config(self, config_path: str) -> None:
        # ЭТАП 1: Загрузка конфигурации
        if not os.path.exists(config_path):
            raise ConfigError(f"Конфигурационный файл не найден: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                param = row.get('parameter', '').strip()
                value = row.get('value', '').strip()
                if param and value:
                    self.config[param] = value
        missing_params = [p for p in self.required_params if p not in self.config]
        if missing_params:
            raise ConfigError(f"Отсутствуют параметры: {', '.join(missing_params)}")

    def display_config(self) -> None:
        # ЭТАП 1: Вывод конфигурации
        print("Конфигурация анализатора пакетов")
        print("=" * 40)
        for param in self.required_params:
            print(f"{param}: {self.config.get(param)}")
        print("=" * 40)

    def get_npm_package_info(self, package_name: str, version: str) -> dict:
        # ЭТАП 2: Получение информации о пакете из npm
        try:
            url = f"https://registry.npmjs.org/{package_name}"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
            if version not in data.get('versions', {}):
                available_versions = list(data.get('versions', {}).keys())[:5]
                raise DependencyError(f"Версия {version} не найдена. Доступные: {', '.join(available_versions)}")
            return data['versions'][version]

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise DependencyError(f"Пакет {package_name} не найден")
            raise DependencyError(f"Ошибка HTTP: {e.reason}")
        except Exception as e:
            raise DependencyError(f"Ошибка получения пакета: {e}")

    def extract_dependencies(self) -> None:
        # ЭТАП 2: Извлечение прямых зависимостей
        package_info = self.get_npm_package_info(
            self.config['package_name'],
            self.config['package_version']
        )
        dependencies = package_info.get('dependencies', {})
        self.dependencies = [f"{name}@{version}" for name, version in dependencies.items()]
        if not self.dependencies:
            self.dependencies = ["Прямые зависимости отсутствуют"]

    def display_dependencies(self) -> None:
        # ЭТАП 2: Вывод прямых зависимостей
        print(f"\nПрямые зависимости {self.config['package_name']}@{self.config['package_version']}:")
        print("-" * 40)
        for dep in self.dependencies:
            print(f"  {dep}")

    def build_dependency_graph(self) -> None:
        # ЭТАП 3: Построение графа зависимостей
        test_mode = self.config['test_repo_mode'].lower() in ('true', 'yes', '1')
        if test_mode:
            self._build_graph_from_file()
        else:
            self._build_graph_from_npm()

    def _build_graph_from_file(self) -> None:
        # ЭТАП 3: Режим тестирования - чтение из файла
        repo_path = self.config['repository_url']
        if not os.path.exists(repo_path):
            raise DependencyError(f"Тестовый файл не найден: {repo_path}")
        try:
            with open(repo_path, 'r', encoding='utf-8') as f:
                self.dependency_graph = json.load(f)
            print(f"\nЗагружен тестовый граф из файла: {repo_path}")
        except Exception as e:
            raise DependencyError(f"Ошибка чтения тестового файла: {e}")

    def _build_graph_from_npm(self) -> None:
        # ЭТАП 3: Режим npm - построение графа DFS без рекурсии
        start_package = self.config['package_name']
        start_version = self.config['package_version']
        stack = deque([(start_package, start_version)])
        self.dependency_graph = {}
        visited = set()
        while stack:
            package, version = stack.pop()
            package_key = f"{package}@{version}"
            if package_key in visited:
                continue

            visited.add(package_key)

            try:
                package_info = self.get_npm_package_info(package, version)
                dependencies = package_info.get('dependencies', {})
                self.dependency_graph[package_key] = [
                    f"{dep_name}@{dep_version}" for dep_name, dep_version in dependencies.items()
                ]
                for dep_name, dep_version in dependencies.items():
                    dep_key = f"{dep_name}@{dep_version}"
                    if dep_key not in visited:
                        stack.append((dep_name, dep_version))

            except DependencyError as e:
                print(f"Предупреждение: не удалось получить зависимости для {package_key}: {e}")
                self.dependency_graph[package_key] = []

    def detect_cycles(self) -> list:
        # ЭТАП 3: Обнаружение циклов DFS без рекурсии
        cycles = []
        for start_node in self.dependency_graph:
            stack = [(start_node, [start_node])]
            visited_in_dfs = set()
            while stack:
                current_node, path = stack.pop()
                if current_node in visited_in_dfs:
                    continue
                visited_in_dfs.add(current_node)
                for neighbor in self.dependency_graph.get(current_node, []):
                    if neighbor in path:
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        if cycle not in cycles:
                            cycles.append(cycle)
                    elif neighbor not in visited_in_dfs:
                        stack.append((neighbor, path + [neighbor]))
        return cycles

    def display_dependency_graph(self) -> None:
        # ЭТАП 3: Вывод полного графа
        print(f"\nПолный граф зависимостей:")
        print("=" * 50)
        for package, dependencies in self.dependency_graph.items():
            print(f"{package}: {', '.join(dependencies)}")

    # ЭТАП 4: Поиск обратных зависимостей
    def find_reverse_dependencies(self, target_package: str) -> list:
        reverse_deps = []
        for package in self.dependency_graph:
            stack = deque([package])
            visited = set()
            while stack:
                current_package = stack.pop()
                if current_package in visited:
                    continue
                visited.add(current_package)
                for dependency in self.dependency_graph.get(current_package, []):
                    if dependency == target_package:
                        if current_package not in reverse_deps:
                            reverse_deps.append(current_package)
                    if dependency not in visited:
                        stack.append(dependency)

        return reverse_deps

    def display_reverse_dependencies(self) -> None:
        #ЭТАП 4: Вывод обратных зависимостей
        target_package = self.config['package_name']
        if self.config['test_repo_mode'].lower() in ('true', 'yes', '1'):
            target_key = target_package
        else:
            target_key = f"{target_package}@{self.config['package_version']}"
        print(f"\nПоиск обратных зависимостей для: {target_key}")
        print("-" * 50)
        reverse_deps = self.find_reverse_dependencies(target_key)
        if reverse_deps:
            print(f"Пакеты, зависящие от {target_key}:")
            for i, dep in enumerate(reverse_deps, 1):
                print(f"  {i}. {dep}")
        else:
            print(f"Нет пакетов, зависящих от {target_key}")

    def run_analysis(self) -> None:
        print(f"\nАнализ пакета: {self.config['package_name']}@{self.config['package_version']}")
        # ЭТАП 2: Прямые зависимости
        self.extract_dependencies()
        self.display_dependencies()
        # ЭТАП 3: Полный граф зависимостей
        self.build_dependency_graph()
        self.display_dependency_graph()
        # ЭТАП 3: Обнаружение циклов
        cycles = self.detect_cycles()
        if cycles:
            print(f"\nОбнаружены циклические зависимости ({len(cycles)}):")
            for i, cycle in enumerate(cycles, 1):
                print(f"Цикл {i}: {' → '.join(cycle)}")
        else:
            print("\nЦиклические зависимости не обнаружены")
        # ЭТАП 4: Обратные зависимости
        self.display_reverse_dependencies()
        # ЭТАП 1: ASCII-дерево если включено
        if self.config.get('ascii_tree_mode', '').lower() in ('true', 'yes', '1'):
            print(f"\nASCII-дерево:")
            print(f"{self.config['package_name']}@{self.config['package_version']}")
            for dep in self.dependencies:
                print(f"└── {dep}")


def main():
    analyzer = PackageAnalyzer()
    try:
        config_path = "config.csv"
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
        analyzer.load_config(config_path)
        analyzer.display_config()  # Этап 1
        analyzer.run_analysis()  # Этапы 2, 3 и 4
    except (ConfigError, DependencyError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()