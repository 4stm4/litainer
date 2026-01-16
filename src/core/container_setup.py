import os
import platform
from pathlib import Path
from core.interfaces import FileSystemPort, LoggerPort, NetworkConfiguratorPort
import shutil
import subprocess

class ContainerSetup:

    def __init__(self, fs: FileSystemPort, logger: LoggerPort, network_configurator: NetworkConfiguratorPort):
        self.fs = fs
        self.logger = logger
        self.network_configurator = network_configurator


    def setup_directories(self, rootfs_path: Path):
        directories = [
            "bin", "boot", "dev", "etc", "home",
            "lib", "media", "mnt", "opt", "proc",
            "root", "run", "sbin", "srv", "sys",
            "tmp", "usr", "var"
        ]
        for directory in directories:
            dir_path = rootfs_path / directory
            self.fs.create_directory(dir_path)
            self.logger.info(f"Создана директория: {dir_path}")

    def copy_system_libraries(self, rootfs_path: Path, libraries: list[Path]):
        for lib in libraries:
            if lib.exists():
                dest = rootfs_path / "lib" / lib.name
                self.fs.copy_file(lib, dest)
                self.logger.info(f"Скопирована библиотека: {lib}")
            else:
                self.logger.error(f"Библиотека не найдена: {lib}")

    def setup_network(self, rootfs_path: Path):
        self.network_configurator.setup_network(rootfs_path)

    def get_library_paths(self):
        """
        Возвращает пути системных библиотек на основе архитектуры.
        """
        arch = platform.machine()
        if arch == "x86_64":
            return [
                Path("/lib/x86_64-linux-gnu/libc.so.6"),
                Path("/lib/x86_64-linux-gnu/libpthread.so.0"),
            ]
        elif arch == "aarch64":  # Архитектура arm64
            return [
                Path("/lib/aarch64-linux-gnu/libc.so.6"),
                Path("/lib/aarch64-linux-gnu/libpthread.so.0"),
            ]
        else:
            raise ValueError(f"Неизвестная архитектура: {arch}")

    def copy_system_libraries(self, rootfs_path: Path):
        libraries = self.get_library_paths()
        for lib in libraries:
            if lib.exists():
                dest = rootfs_path / "lib" / lib.name
                self.fs.copy_file(lib, dest)
                self.logger.info(f"Скопирована библиотека: {lib}")
            else:
                self.logger.error(f"Библиотека не найдена: {lib}")

    def copy_binaries_and_dependencies(self, rootfs_path: Path, binaries: list[str]):
        for binary in binaries:
            # Найти путь к бинарнику
            result = subprocess.run(["which", binary], capture_output=True, text=True)
            binary_path = result.stdout.strip()
            if not binary_path or not Path(binary_path).exists():
                self.logger.error(f"Бинарник {binary} не найден!")
                continue
            # Копировать бинарник
            dest_bin = rootfs_path / "bin" / Path(binary_path).name
            dest_bin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary_path, dest_bin)
            self.logger.info(f"Скопирован бинарник: {binary_path} -> {dest_bin}")
            # Найти и скопировать зависимости
            ldd_result = subprocess.run(["ldd", binary_path], capture_output=True, text=True)
            for line in ldd_result.stdout.splitlines():
                parts = line.strip().split(" => ")
                if len(parts) == 2:
                    lib_path = parts[1].split()[0]
                elif "/" in line:
                    lib_path = line.strip().split()[0]
                else:
                    continue
                lib_path = lib_path.strip()
                if Path(lib_path).exists():
                    dest_lib = rootfs_path / "lib" / Path(lib_path).name
                    dest_lib.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(lib_path, dest_lib)
                    self.logger.info(f"Скопирована зависимость: {lib_path} -> {dest_lib}")
                else:
                    self.logger.error(f"Зависимость {lib_path} не найдена!")

    def detach_image(self, device: str):
        subprocess.run(["hdiutil", "detach", device], check=True)
