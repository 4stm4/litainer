import os
import subprocess
import tarfile
import logging
import requests
from bs4 import BeautifulSoup


RPI_REPO_URL = "https://github.com/raspberrypi/linux.git"

class LinuxKernel:
    kernel_version: str = "6.6.9"
    rpi_model: str
    temp_path: str
    kernel_file: str
    rpi_repo_path: str

    def __init__(self, temp_path: str, rpi_model: str):
        self.kernel_version = self._get_latest_kernel_version()
        self.temp_path = temp_path
        self.rpi_model = rpi_model
        self.kernel_file = f"{self.temp_path}/linux-{self.kernel_version}.tar.xz"
        self.rpi_repo_path = os.path.join(self.temp_path, "rpi_linux")

    @staticmethod
    def _get_latest_kernel_version() -> str:
        url = "https://www.kernel.org/"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Проверка на ошибки HTTP
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем элемент с последней стабильной версией ядра
            latest_version = soup.find('td', {'id': 'latest_link'}).text.strip()
            return latest_version
        except requests.RequestException as e:
            logging.error(f"Ошибка при подключении к {url}: {e}")
            return None
        except Exception as e:
            logging.error(f"Не удалось извлечь версию ядра: {e}")
            return None

    def download_kernel(self):
        """Скачиваем исходный код ядра Linux в директорию temp_path."""
        logging.info(f"Скачиваем ядро Linux версии {self.kernel_version}...")

        url = f"https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-{self.kernel_version}.tar.xz"

        if not os.path.exists(self.kernel_file):
            try:
                subprocess.run(["wget", "-P", self.temp_path, url], check=True)

                logging.info(f"Ядро загружено: {self.kernel_file}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Ошибка при загрузке ядра: {e}")
                raise
        else:
            logging.info(f"Архив ядра уже существует: {self.kernel_file}")

    def unpack_kernel(self):
        """Распаковываем исходный код ядра с использованием tarfile."""
        logging.info(f"Распаковываем ядро версии {self.kernel_version}...")
        
        # Определяем директорию, куда будет распаковано ядро
        target_directory = os.path.join(self.temp_path, f"linux-{self.kernel_version}")
        
        # Проверяем, существует ли целевая директория
        if os.path.exists(target_directory):
            logging.info("Директория с исходным кодом уже существует.")
            return

        # Распаковываем архив
        try:
            with tarfile.open(self.kernel_file, "r:xz") as tar:
                logging.info(f"Распаковываем {self.kernel_file} в {self.temp_path}")
                tar.extractall(path=self.temp_path)
                logging.info(f"Ядро успешно распаковано в {target_directory}")
        except FileNotFoundError:
            logging.error(f"Файл {self.kernel_file} не найден!")
            raise
        except tarfile.TarError as e:
            logging.error(f"Ошибка при распаковке архива: {e}")
            raise

    def _use_rpi_config(self):
        """
        Клонирует репозиторий Raspberry Pi и копирует конфигурацию ядра для указанной модели.
        
        :param kernel_version: Версия ядра Linux.
        :param rpi_model: Конфигурация для определённой модели Raspberry Pi.
        """
        logging.info("Клонируем репозиторий Raspberry Pi для получения конфигурации...")
   
        # Создаём директорию, если её ещё нет
        if not os.path.exists(self.rpi_repo_path):
            os.makedirs(self.rpi_repo_path, exist_ok=True)
            logging.info(f"Директория {self.rpi_repo_path} успешно создана.")

        # Проверяем, есть ли внутри директории репозиторий Git
        git_dir = os.path.join(self.rpi_repo_path, ".git")
        if not os.path.exists(git_dir):
            logging.info(f"Клонируем репозиторий Raspberry Pi в {self.rpi_repo_path}...")
            subprocess.run(["git", "clone", "--depth=1", RPI_REPO_URL, self.rpi_repo_path], check=True)
        else:
            logging.info("Репозиторий Raspberry Pi уже клонирован.")

        # Проверяем, существует ли нужный файл конфигурации для arm64
        rpi_config_path = os.path.join(self.rpi_repo_path, "arch/arm64/configs", self.rpi_model)
        if not os.path.exists(rpi_config_path):
            logging.info(f"Конфигурация {self.rpi_model} не найдена в arch/arm64/configs, ищем в arm/configs...")
            rpi_config_path = os.path.join(self.rpi_repo_path, "arch/arm/configs", self.rpi_model)
            if not os.path.exists(rpi_config_path):
                raise FileNotFoundError(f"Конфигурация {self.rpi_model} не найдена в репозитории Raspberry Pi!")

        # # Копируем конфигурацию в текущую директорию ядра
        # kernel_config_path = "arch/arm64/configs/defconfig"
        # logging.info(f"Копируем {self.rpi_model} в {kernel_config_path}...")
        # subprocess.run(["cp", rpi_config_path, kernel_config_path], check=True)

        # Настраиваем ядро с этой конфигурацией
        logging.info(f"Используем конфигурацию для настройки ядра...")
        subprocess.run(["make", "ARCH=arm64", self.rpi_model], check=True, cwd=self.rpi_repo_path)

    def configure_kernel(self):
        """
        Настраиваем ядро для ARM64 с использованием либо стандартной конфигурации,
        либо конфигурации Raspberry Pi.
        """
        logging.info("Настраиваем параметры ядра для ARM64...")

        try:
            self._use_rpi_config()
        except FileNotFoundError as e:
            logging.error(f"Ошибка: {e}. Переходим к стандартной конфигурации.")
            subprocess.run(["make", "ARCH=arm64", "defconfig"], check=True)

        # Применяем дополнительные изменения
        with open(".config", "a") as config_file:
            config_file.write("\n")
            config_file.write("# Custom kernel configuration for Raspberry Pi\n")
            config_file.write("CONFIG_CGROUPS=y\n")
            config_file.write("CONFIG_NAMESPACES=y\n")
            config_file.write("CONFIG_OVERLAY_FS=y\n")
            config_file.write("CONFIG_TMPFS=y\n")
            config_file.write("CONFIG_IPV6=y\n")
        subprocess.run(["make", "ARCH=arm64", "olddefconfig"], check=True, cwd=self.rpi_repo_path)


    def compile_kernel(self):
        """Компилируем ядро, если оно не скомпилировано."""
        kernel_path = "arch/arm64/boot/Image"  # Путь к скомпилированному ядру
        if not os.path.exists(kernel_path):
            logging.info("Ядро не найдено, начинаем компиляцию...")
            # Получаем количество доступных процессоров для оптимизации сборки
            nproc = os.cpu_count()

            # Запускаем команду make с использованием параллельной сборки
            subprocess.run(["make", f"-j{nproc}"], check=True, cwd=self.rpi_repo_path)
        else:
            logging.info("Ядро уже скомпилировано, пропускаем компиляцию.")

    def install_kernel(self):
        """Устанавливаем ядро в систему."""
        logging.info("Устанавливаем ядро...")
        subprocess.run(["sudo", "make", "modules_install"], check=True, cwd=self.rpi_repo_path)
        subprocess.run(["sudo", "make", "install"], check=True, cwd=self.rpi_repo_path)
