from core.container_setup import ContainerSetup
from adapters.file_adapter import FileAdapter
from adapters.logging_adapter import LoggingAdapter
from adapters.network_adapter import NetworkAdapter
from adapters.package_installer import PackageInstaller, install_dependencies
from adapters.linux_kernel import LinuxKernel
from pathlib import Path


# Определение абсолютных путей
SCRIPT_DIR = Path(__file__).parent.absolute()
TEMP_PATH = SCRIPT_DIR.parent / "temp"
ROOTFS_PATH = SCRIPT_DIR.parent / "container"
RPI_MODEL = "bcm2711_defconfig"

if __name__ == "__main__":
    # Инициализация адаптеров
    file_adapter = FileAdapter(ROOTFS_PATH)
    logging_adapter = LoggingAdapter()
    network_adapter = NetworkAdapter()
    linux_kernel = LinuxKernel(TEMP_PATH, RPI_MODEL)
    package_installer = PackageInstaller(TEMP_PATH, ROOTFS_PATH)

    file_adapter.clear_container()
    print('_______________')
    # Инициализация контейнера
    setup = ContainerSetup(file_adapter, logging_adapter, network_adapter)
    linux_kernel.download_kernel()
    linux_kernel.unpack_kernel()
    install_dependencies()
    linux_kernel.configure_kernel()
    linux_kernel.compile_kernel()
    linux_kernel.install_kernel()
    # Настройка контейнера
    setup.setup_directories(ROOTFS_PATH)
    try:
        setup.copy_system_libraries(ROOTFS_PATH)
    except ValueError as e:
        logging_adapter.error(str(e))
    setup.setup_network(ROOTFS_PATH)

    # Список пакетов для установки
    packages = ["bash", "coreutils", "curl", "vim"]
    package_installer.install_base_packages(packages)
    setup.copy_binaries_and_dependencies(ROOTFS_PATH, packages)
