import subprocess
from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).parent.parent
IMG_PATH = PROJECT_ROOT / "raspi.img"
KERNEL_IMAGE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/Image"
DTB_FILE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/dts" / "broadcom" / "bcm2710-rpi-3-b-plus.dtb"

QEMU_CMD = "qemu-system-aarch64"

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
        "-append", "console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4 rw",
        "-serial", "stdio",
        "-no-reboot"
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(line, end="")
            if "login:" in line or "Welcome" in line or "bash" in line:
                print("QEMU: Система загрузилась успешно!")
                proc.terminate()
                sys.exit(0)
        proc.wait(timeout=60)
    except Exception as e:
        print(f"ОШИБКА при запуске QEMU: {e}")
        sys.exit(1)
    print("QEMU завершил работу. Проверьте вывод выше.")

if __name__ == "__main__":
    check_requirements()
    run_qemu() 