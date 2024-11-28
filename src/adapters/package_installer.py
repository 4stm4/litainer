import os
import sys
import tarfile
import logging
import subprocess
from pathlib import Path
from typing import List
import glob

class PackageInstaller:
    """
    Установщик пакетов в контейнер.
    """
    temp_path: Path
    rootfs_path: Path

    def __init__(self, temp_path: str, rootfs_path: str):
        """
        Инициализирует установщик пакетов.

        Args:
            temp_path: Путь к временной директории.
            rootfs_path: Путь к директории rootfs контейнера.
        """
        self.temp_path = Path(temp_path)
        self.rootfs_path = Path(rootfs_path)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    def _install_deb(self, deb_path: Path):
        """
        Устанавливает .deb пакет в директорию rootfs контейнера.

        Args:
            deb_path: Путь к .deb файлу.
        """
        if not deb_path.exists():
            logging.error(f"Файл {deb_path} не найден!")
            return

        try:
            subprocess.run(["ar", "x", str(deb_path)], cwd=self.temp_path, check=True)

            data_file = self.temp_path / "data.tar.xz"
            if not data_file.exists():
                logging.error(f"Файл {data_file} не найден в {deb_path}!")
                return

            with tarfile.open(data_file, mode="r:xz") as tar:
                tar.extractall(path=self.rootfs_path)
            logging.info(f"Пакет {deb_path.name} успешно установлен.")

        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка при распаковке пакета {deb_path.name}: {e}")
        except tarfile.ReadError as e:
            logging.error(f"Ошибка при чтении tar архива {data_file}: {e}")
        finally:
            # Очистка временных файлов
            if data_file.exists():
                data_file.unlink()
            for file in self.temp_path.glob("*.deb"):
                file.unlink()

    def _download_and_install_package(self, package_name: str):
        """
        Загружает и устанавливает пакет из репозитория.

        Args:
            package_name: Имя пакета.
        """
        logging.info(f"Загружаем и устанавливаем пакет {package_name}...")
        try:
            if not self._is_apt_get_available():
                raise EnvironmentError("apt-get не найден. Убедитесь, что он установлен и доступен в PATH.")
            subprocess.run(
                ["apt-get", "download", "-y",  package_name],
                cwd=self.temp_path,
                check=True,
                capture_output=True,
                text=True
            )

            deb_files = list(self.temp_path.glob(f"{package_name}*.deb"))
            if not deb_files:
                raise FileNotFoundError(f"Не найден .deb файл для пакета {package_name}")
            for deb_file in deb_files:
                self._install_deb(deb_file)
            

        except subprocess.CalledProcessError as e:
            logging.error(f"Ошибка при загрузке пакета {package_name}: {e.stderr}")
            raise
        except EnvironmentError as e:
            logging.error(f"Ошибка окружения: {e}")
            raise
        except FileNotFoundError as e:
            logging.error(f"Ошибка: {e}")
            raise

    def install_base_packages(self, packages: List[str]):
        """
        Устанавливает базовые пакеты в контейнер.

        Args:
            packages: Список имен пакетов.
        """
        logging.info("Устанавливаем базовые пакеты в контейнер...")

        for package in packages:
            deb_files = list(self.temp_path.glob(f"{package}_*.deb"))
            if deb_files:
                #берем последний скаченный файл
                deb_file = sorted(deb_files, key=os.path.getmtime)[-1]
                logging.info(f"Пакет {package} найден в {self.temp_path}, установка")
                self._install_deb(deb_file)
            else:
                self._download_and_install_package(package)

        logging.info("Базовые пакеты установлены.")

    def _is_apt_get_available(self) -> bool:
        """Проверяет, доступен ли apt-get в системе."""
        try:
            subprocess.run(["apt-get", "--version"], check=True, capture_output=True)
            return True
        except FileNotFoundError:
            return False
        except subprocess.CalledProcessError:
            return True

def install_dependencies():
    """Устанавливаем необходимые зависимости для сборки ядра."""
    logging.info("Устанавливаем зависимости...")
    
    # Сначала устанавливаем gpgv
    try:
        subprocess.run(["sudo", "apt-get", "install", "-y", "gpgv2"], check=True)
    except subprocess.CalledProcessError:
        logging.error("Ошибка при установке gpgv")
        sys.exit(1)
        
    dependencies = [
        "build-essential",
        "libncurses-dev",
        "bison",
        "flex",
        "libssl-dev",
        "bc",
        "git",
    ]
    
    # Затем устанавливаем остальные зависимости
    try:
        # subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y"] + dependencies, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при установке зависимостей: {e}")
        sys.exit(1)