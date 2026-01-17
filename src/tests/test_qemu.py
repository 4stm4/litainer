import subprocess
import sys
import os
import time
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
IMG_PATH = PROJECT_ROOT / "raspi.img"
KERNEL_IMAGE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/Image"
DTB_FILE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/dts" / "broadcom" / "bcm2710-rpi-3-b-plus.dtb"

QEMU_CMD = "qemu-system-aarch64"
READY_MARKERS = {"OVSDB_STARTED", "NET_AGENT_STARTED"}

# Добавить путь к util-linux от Homebrew в PATH
brew_prefix = subprocess.run(["brew", "--prefix"], capture_output=True, text=True).stdout.strip()
util_linux_bin = f"{brew_prefix}/opt/util-linux/bin"
os.environ["PATH"] = util_linux_bin + ":" + os.environ["PATH"]

def check_requirements():
    # Проверка наличия qemu
    try:
        subprocess.run([QEMU_CMD, "--version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("ОШИБКА: qemu-system-aarch64 не найден. Установите qemu-system-aarch64.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("ОШИБКА: qemu-system-aarch64 установлен некорректно.")
        sys.exit(1)
    # Проверка наличия образа
    if not IMG_PATH.exists():
        print(f"ОШИБКА: Образ {IMG_PATH} не найден. Сначала создайте его через make_image.py.")
        sys.exit(1)
    # Проверка ядра
    if not KERNEL_IMAGE.exists():
        print(f"ОШИБКА: Ядро {KERNEL_IMAGE} не найдено. Сначала соберите ядро.")
        sys.exit(1)
    # Проверка dtb
    if not DTB_FILE.exists():
        print(f"ОШИБКА: DTB-файл {DTB_FILE} не найден. Проверьте сборку ядра и путь к dtb.")
        sys.exit(1)


def run_qemu():
    print("Запускаем QEMU...")
    cmd = [
        QEMU_CMD,
        "-M", "raspi3",
        "-m", "1024",
        "-kernel", str(KERNEL_IMAGE),
        "-dtb", str(DTB_FILE),
        "-drive", f"file={IMG_PATH},format=raw,if=sd",
        "-append", "console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4 rw init=/etc/init.d/rcS",
        "-netdev", "user,id=net0,hostfwd=tcp::6640-:6640",
        "-device", "virtio-net-pci,netdev=net0",
        "-serial", "stdio",
        "-no-reboot"
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        seen = set()
        start = time.time()
        for line in proc.stdout:
            print(line, end="")
            for marker in READY_MARKERS:
                if marker in line:
                    seen.add(marker)
            if "Kernel panic" in line:
                print("ОШИБКА: Kernel panic в гостевой системе.")
                proc.terminate()
                sys.exit(1)
            if seen == READY_MARKERS:
                # Проверяем доступность OVSDB по hostfwd на 6640
                try:
                    with socket.create_connection(("127.0.0.1", 6640), timeout=5) as s:
                        print("QEMU: ovsdb-server доступен на tcp/6640 (hostfwd).")
                        proc.terminate()
                        sys.exit(0)
                except Exception as e:
                    print(f"ОШИБКА: не удалось подключиться к ovsdb-server: {e}")
                    proc.terminate()
                    sys.exit(1)
            if time.time() - start > 180:
                print("ОШИБКА: таймаут ожидания маркеров запуска ovsdb-server.")
                proc.terminate()
                sys.exit(1)
        proc.wait(timeout=30)
    except Exception as e:
        print(f"ОШИБКА при запуске QEMU: {e}")
        sys.exit(1)
    print("QEMU завершил работу. Проверьте вывод выше.")

if __name__ == "__main__":
    check_requirements()
    run_qemu() 
