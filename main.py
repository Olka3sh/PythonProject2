import csv
import os
import sys

class ConfigError(Exception):
    pass

class PackageAnalyzer:
    def __init__(self):
        self.config = {}
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

def main():
    analyzer = PackageAnalyzer()

    try:
        config_path = "config.csv"
        if len(sys.argv) > 1:
            config_path = sys.argv[1]

        analyzer.load_config(config_path)
        analyzer.display_config()

    except ConfigError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()