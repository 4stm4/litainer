import os
import subprocess
from pathlib import Path

IMG_SIZE_MB = 2048  # Размер образа в мегабайтах
IMG_NAME = "raspi.img"
BOOT_SIZE_MB = 256  # Размер boot-раздела

PROJECT_ROOT = Path(__file__).parent.parent
CONTAINER_PATH = PROJECT_ROOT / "container"
TEMP_PATH = PROJECT_ROOT / "temp"
IMG_PATH = PROJECT_ROOT / IMG_NAME

BOOT_MNT = TEMP_PATH / "mnt_boot"
ROOTFS_MNT = TEMP_PATH / "mnt_rootfs"

# Пути к файлам ядра и конфигам (замените на свои при необходимости)
KERNEL_IMAGE = TEMP_PATH / "rpi_linux" / "arch/arm64/boot/Image"
DTB_DIR = TEMP_PATH / "rpi_linux" / "arch/arm64/boot/dts"
CONFIG_TXT = TEMP_PATH / "config.txt"
CMDLINE_TXT = TEMP_PATH / "cmdline.txt"

def run(cmd):
    print(f"$ {' '.join(str(x) for x in cmd)}")
    subprocess.run(cmd, check=True)

def create_img():
    TEMP_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Создаём пустой образ {IMG_PATH} размером {IMG_SIZE_MB}MB...")
    run(["dd", "if=/dev/zero", f"of={IMG_PATH}", "bs=1M", f"count={IMG_SIZE_MB}"])

    print("Размечаем образ (boot + rootfs)...")
    sfdisk_input = f"""
label: dos
label-id: 0x0
unit: sectors

/dev/sda1 : start=2048, size={BOOT_SIZE_MB*2048}, type=c
/dev/sda2 : start={BOOT_SIZE_MB*2048+2048}, type=83
""".strip()
    with open(TEMP_PATH / "partition.sfdisk", "w") as f:
        f.write(sfdisk_input)
    run(["sfdisk", IMG_PATH, "<", str(TEMP_PATH / "partition.sfdisk")])

    print("Подключаем loop-устройство...")
    run(["losetup", "-Pf", IMG_PATH])
    loopdev = subprocess.check_output(["losetup", "-j", str(IMG_PATH)]).decode().split(":")[0]
    boot_part = f"{loopdev}p1"
    rootfs_part = f"{loopdev}p2"

    print("Создаём файловые системы...")
    run(["mkfs.vfat", boot_part])
    run(["mkfs.ext4", rootfs_part])

    BOOT_MNT.mkdir(parents=True, exist_ok=True)
    ROOTFS_MNT.mkdir(parents=True, exist_ok=True)
    run(["mount", boot_part, BOOT_MNT])
    run(["mount", rootfs_part, ROOTFS_MNT])

    print("Копируем rootfs...")
    run(["cp", "-a", str(CONTAINER_PATH) + "/.", str(ROOTFS_MNT)])

    print("Копируем boot-файлы...")
    # Генерируем config.txt и cmdline.txt, если их нет
    if not CONFIG_TXT.exists():
        CONFIG_TXT.write_text("kernel=kernel8.img\nenable_uart=1\n")
        print(f"Создан {CONFIG_TXT}")
    if not CMDLINE_TXT.exists():
        CMDLINE_TXT.write_text("console=serial0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 fsck.repair=yes rootwait\n")
        print(f"Создан {CMDLINE_TXT}")
    if KERNEL_IMAGE.exists():
        run(["cp", str(KERNEL_IMAGE), str(BOOT_MNT / "kernel8.img")])
    if CONFIG_TXT.exists():
        run(["cp", str(CONFIG_TXT), str(BOOT_MNT / "config.txt")])
    if CMDLINE_TXT.exists():
        run(["cp", str(CMDLINE_TXT), str(BOOT_MNT / "cmdline.txt")])
    # Копировать dtb-файлы (если есть)
    if DTB_DIR.exists():
        run(["cp", "-a", str(DTB_DIR), str(BOOT_MNT)])

    print("Размонтируем...")
    run(["umount", BOOT_MNT])
    run(["umount", ROOTFS_MNT])
    run(["losetup", "-d", loopdev])
    print(f"Готово! Образ: {IMG_PATH}")

if __name__ == "__main__":
    create_img() 