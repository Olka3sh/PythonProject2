import csv
import os
import sys
import json
import urllib.request
import urllib.error


class ConfigError(Exception):
    pass


class DependencyError(Exception):
    pass


class PackageAnalyzer:
    def __init__(self):
        self.config = {}
        self.dependencies = []
        self.required_params = [
            'package_name',
            'repository_url',
            'test_repo_mode',
            'package_version',
            'output_filename',
            'ascii_tree_mode'
        ]

    def load_config(self, config_path: str) -> None:
        if not os.path.exists(config_path):
            raise ConfigError(f"Конфигурационный файл не найден: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                param = row.get('parameter', '').strip()
                value = row.get('value', '').strip()
                if param and value:
                    self.config[param] = value

        # Проверка обязательных параметров
        missing_params = [p for p in self.required_params if p not in self.config]
        if missing_params:
            raise ConfigError(f"Отсутствуют параметры: {', '.join(missing_params)}")

    def display_config(self) -> None:
        print("Конфигурация анализатора пакетов")
        print("=" * 40)
        for param in self.required_params:
            print(f"{param}: {self.config.get(param)}")
        print("=" * 40)

    def get_npm_package_info(self) -> dict:
        package_name = self.config['package_name']
        version = self.config['package_version']

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
        package_info = self.get_npm_package_info()

        dependencies = package_info.get('dependencies', {})

        self.dependencies = [f"{name}@{version}" for name, version in dependencies.items()]

        if not self.dependencies:
            self.dependencies = ["Прямые зависимости отсутствуют"]

    def display_dependencies(self) -> None:
        print(f"\nПрямые зависимости {self.config['package_name']}@{self.config['package_version']}:")
        print("-" * 40)
        for dep in self.dependencies:
            print(f"  {dep}")

    def run_analysis(self) -> None:
        print(f"\nАнализ пакета: {self.config['package_name']}@{self.config['package_version']}")

        self.extract_dependencies()
        self.display_dependencies()

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
        analyzer.display_config()      # Этап 1
        analyzer.run_analysis()        # Этап 2 - ДОБАВИТЬ ЭТУ СТРОКУ

    except (ConfigError, DependencyError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()