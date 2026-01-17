import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Union


RPI_REPO_URL = "https://github.com/raspberrypi/linux.git"

class LinuxKernel:
    rpi_model: str
    temp_path: Path
    rpi_repo_path: Path
    kernel_image: Path
    rootfs_path: Path

    def __init__(self, temp_path: str, rpi_model: str, rootfs_path: Union[Path, str]):
        self.temp_path = Path(temp_path)
        self.rpi_model = rpi_model
        self.rpi_repo_path = self.temp_path / "rpi_linux"
        self.kernel_image = self.rpi_repo_path / "arch/arm64/boot/Image"
        self.rootfs_path = Path(rootfs_path)

    def download_kernel(self):
        """Клонирует или обновляет исходники ядра Raspberry Pi."""
        logging.info("Готовим исходники ядра Raspberry Pi...")
        self.temp_path.mkdir(parents=True, exist_ok=True)

        git_dir = self.rpi_repo_path / ".git"
        if not git_dir.exists():
            logging.info(f"Клонируем {RPI_REPO_URL} в {self.rpi_repo_path}")
            subprocess.run(
                ["git", "clone", "--depth=1", RPI_REPO_URL, str(self.rpi_repo_path)],
                check=True,
                cwd=self.temp_path,
            )
            return

        logging.info("Репозиторий уже клонирован, обновляем...")
        subprocess.run(["git", "pull", "--ff-only"], check=True, cwd=self.rpi_repo_path)

    def unpack_kernel(self):
        """Совместимость с прежним API: исходники уже в git-репозитории."""
        logging.info(f"Исходники доступны в {self.rpi_repo_path}")

    def _use_rpi_config(self):
        """
        Готовит конфигурацию ядра для указанной модели Raspberry Pi.
        """
        if not (self.rpi_repo_path / ".git").exists():
            raise FileNotFoundError(f"Репозиторий ядра не найден: {self.rpi_repo_path}")

        rpi_config_path = self.rpi_repo_path / "arch" / "arm64" / "configs" / self.rpi_model
        if not rpi_config_path.exists():
            logging.info(f"Конфигурация {self.rpi_model} не найдена в arch/arm64/configs, ищем в arm/configs...")
            rpi_config_path = self.rpi_repo_path / "arch" / "arm" / "configs" / self.rpi_model
            if not rpi_config_path.exists():
                raise FileNotFoundError(f"Конфигурация {self.rpi_model} не найдена в репозитории Raspberry Pi!")

        logging.info("Используем конфигурацию для настройки ядра...")
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
            subprocess.run(["make", "ARCH=arm64", "defconfig"], check=True, cwd=self.rpi_repo_path)

        # Применяем дополнительные изменения
        config_path = self.rpi_repo_path / ".config"
        with config_path.open("a") as config_file:
            config_file.write("\n")
            config_file.write("# Custom kernel configuration for Raspberry Pi\n")
            config_file.write("CONFIG_CGROUPS=y\n")
            config_file.write("CONFIG_NAMESPACES=y\n")
            config_file.write("CONFIG_OVERLAY_FS=y\n")
            config_file.write("CONFIG_TMPFS=y\n")
            config_file.write("CONFIG_IPV6=y\n")
            config_file.write("CONFIG_KVM=y\n")
            config_file.write("CONFIG_VHOST_NET=y\n")
            config_file.write("CONFIG_VFIO=y\n")
            config_file.write("CONFIG_VFIO_PCI=y\n")
            config_file.write("CONFIG_ISCSI_TCP=y\n")
            config_file.write("CONFIG_MULTIPATH=y\n")
            config_file.write("CONFIG_WATCHDOG=y\n")
        subprocess.run(["make", "ARCH=arm64", "olddefconfig"], check=True, cwd=self.rpi_repo_path)


    def compile_kernel(self):
        """Компилируем ядро, если оно не скомпилировано."""
        kernel_path = self.kernel_image  # Путь к скомпилированному ядру
        if not kernel_path.exists():
            logging.info("Ядро не найдено, начинаем компиляцию...")
            # Получаем количество доступных процессоров для оптимизации сборки
            nproc = os.cpu_count() or 1

            # Запускаем команду make с использованием параллельной сборки
            subprocess.run(["make", f"-j{nproc}"], check=True, cwd=self.rpi_repo_path)
        else:
            logging.info("Ядро уже скомпилировано, пропускаем компиляцию.")

    def install_kernel(self):
        """Устанавливаем модули в rootfs и копируем Image/DTB в /boot."""
        logging.info("Устанавливаем модули ядра в rootfs...")
        subprocess.run(
            ["make", "ARCH=arm64", f"INSTALL_MOD_PATH={self.rootfs_path}", "modules_install"],
            check=True,
            cwd=self.rpi_repo_path,
        )

        boot_dir = self.rootfs_path / "boot"
        boot_dir.mkdir(parents=True, exist_ok=True)

        if self.kernel_image.exists():
            dest_image = boot_dir / "kernel8.img"
            shutil.copy2(self.kernel_image, dest_image)
            logging.info(f"Скопирован Image в {dest_image}")
        else:
            logging.error(f"Image не найден: {self.kernel_image}")

        dtb_src_dir = self.rpi_repo_path / "arch" / "arm64" / "boot" / "dts"
        if dtb_src_dir.exists():
            dest_dtb_dir = boot_dir / "dts"
            if dest_dtb_dir.exists():
                shutil.rmtree(dest_dtb_dir)
            shutil.copytree(dtb_src_dir, dest_dtb_dir)
            logging.info(f"Скопированы DTB-файлы в {dest_dtb_dir}")
        else:
            logging.error(f"DTB директория не найдена: {dtb_src_dir}")
