from core.container_setup import ContainerSetup
from adapters.file_adapter import FileAdapter
from adapters.logging_adapter import LoggingAdapter
from adapters.network_adapter import NetworkAdapter
from adapters.package_installer import PackageInstaller, install_dependencies
from adapters.linux_kernel import LinuxKernel
from make_image import create_img
from pathlib import Path


# Определение абсолютных путей
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
TEMP_PATH = PROJECT_ROOT / "temp"
ROOTFS_PATH = PROJECT_ROOT / "container"
RPI_MODEL = "bcm2711_defconfig"
SCHEMA_PATH = SCRIPT_DIR / "schema" / "system.ovsschema"
NET_AGENT_PATH = SCRIPT_DIR / "agents" / "net_agent.py"
STORAGE_AGENT_PATH = SCRIPT_DIR / "agents" / "storage_agent.py"
VM_AGENT_PATH = SCRIPT_DIR / "agents" / "vm_agent.py"
STAT_AGENT_PATH = SCRIPT_DIR / "agents" / "stat_agent.py"
CLI_PATH = SCRIPT_DIR / "cli.py"

if __name__ == "__main__":
    # Инициализация адаптеров
    file_adapter = FileAdapter(ROOTFS_PATH)
    logging_adapter = LoggingAdapter()
    network_adapter = NetworkAdapter()
    linux_kernel = LinuxKernel(TEMP_PATH, RPI_MODEL, ROOTFS_PATH)
    package_installer = PackageInstaller(TEMP_PATH, ROOTFS_PATH)

    file_adapter.clear_container()
    ROOTFS_PATH.mkdir(parents=True, exist_ok=True)
    print('_______________')
    # Инициализация контейнера
    setup = ContainerSetup(file_adapter, logging_adapter, network_adapter)
    linux_kernel.download_kernel()
    linux_kernel.unpack_kernel()
    install_dependencies()
    linux_kernel.configure_kernel()
    linux_kernel.compile_kernel()
    # Настройка контейнера
    setup.setup_directories(ROOTFS_PATH)
    setup.write_base_configs(ROOTFS_PATH, hostname="litainer")
    try:
        setup.copy_system_libraries(ROOTFS_PATH)
    except ValueError as e:
        logging_adapter.error(str(e))
    setup.setup_network(ROOTFS_PATH)
    setup.create_dev_nodes(ROOTFS_PATH)
    linux_kernel.install_kernel()

    # Список пакетов для установки
    packages = [
        "bash",
        "coreutils",
        "curl",
        "vim",
        "iproute2",
        "openvswitch-common",
        "openvswitch-switch",
        "python3-ovs",
        "qemu-system-aarch64",
        "iscsitarget",
        "socat",
    ]
    package_installer.install_base_packages(packages)
    binaries = [
        "bash",
        "coreutils",
        "curl",
        "vim",
        "ip",
        "ldd",
        "ovsdb-server",
        "ovs-vsctl",
        "ovs-vswitchd",
        "python3",
    ]
    setup.copy_binaries_and_dependencies(ROOTFS_PATH, binaries)
    setup.install_ovsdb_assets(
        ROOTFS_PATH,
        SCHEMA_PATH,
        NET_AGENT_PATH,
        storage_agent=STORAGE_AGENT_PATH,
        vm_agent=VM_AGENT_PATH,
        stat_agent=STAT_AGENT_PATH,
        cli_tool=CLI_PATH,
    )
    try:
        create_img()
    except Exception as e:
        logging_adapter.error(f"Не удалось создать образ: {e}")
