import os
import platform
from pathlib import Path
from core.interfaces import FileSystemPort, LoggerPort, NetworkConfiguratorPort

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
