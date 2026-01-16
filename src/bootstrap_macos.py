import subprocess
import sys
import shutil
from pathlib import Path
import os

# Добавить путь к util-linux от Homebrew в PATH
try:
    brew_prefix = subprocess.run(["brew", "--prefix"], capture_output=True, text=True).stdout.strip()
    util_linux_bin = f"{brew_prefix}/opt/util-linux/bin"
    if util_linux_bin not in os.environ["PATH"]:
        os.environ["PATH"] = util_linux_bin + ":" + os.environ["PATH"]
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
SRC_PATH = PROJECT_ROOT / "src"
IMG_PATH = PROJECT_ROOT / "raspi.img"
KERNEL_IMAGE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/Image"
DTB_FILE = PROJECT_ROOT / "temp" / "rpi_linux" / "arch/arm64/boot/dts" / "broadcom" / "bcm2710-rpi-3-b-plus.dtb"

REQUIRED_TOOLS = [
    ("brew", "Homebrew", "https://brew.sh/"),
    ("sfdisk", "util-linux", "brew install util-linux"),
    ("qemu-system-aarch64", "qemu", "brew install qemu"),
    ("losetup", "util-linux", "brew install util-linux"),
    ("mount", "macOS mount", None),
    ("hdiutil", "macOS hdiutil", None),
]

def check_tool(tool, pkg, install_hint):
    if shutil.which(tool) is None:
        print(f"[!] Не найдено: {tool} ({pkg})")
        if install_hint:
            print(f"    Установите: {install_hint}")
        return False
    return True

def auto_install_tools(missing_tools):
    brew_path = shutil.which("brew")
    if not brew_path:
        print("[!] Homebrew не найден. Установите его вручную: https://brew.sh/")
        sys.exit(1)
    pkgs = set()
    for tool, pkg, hint in missing_tools:
        if pkg and pkg != "Homebrew":
            pkgs.add(pkg)
    if not pkgs:
        return
    print(f"[?] Необходима установка: {' '.join(pkgs)} через brew. Продолжить? [Y/n]")
    ans = input().strip().lower()
    if ans and ans not in ("y", "yes", "д", "да", ""):
        print("[!] Установка отменена пользователем.")
        sys.exit(1)
    for pkg in pkgs:
        print(f"[+] brew install {pkg}")
        res = subprocess.run([brew_path, "install", pkg])
        if res.returncode != 0:
            print(f"[!] Ошибка установки {pkg}")
            sys.exit(1)
    print("[+] Установка завершена. Продолжаем...\n")

def check_all_tools():
    print("[+] Проверка необходимых утилит...")
    all_ok = True
    missing = []
    for tool, pkg, hint in REQUIRED_TOOLS:
        if not check_tool(tool, pkg, hint):
            all_ok = False
            missing.append((tool, pkg, hint))
    if not all_ok:
        auto_install_tools(missing)
        # Повторная проверка
        for tool, pkg, hint in REQUIRED_TOOLS:
            if not check_tool(tool, pkg, hint):
                print(f"[!] {tool} всё ещё не найден. Установите вручную.")
                sys.exit(1)
    print("[+] Все необходимые утилиты найдены!\n")

def check_file(path, description):
    if not path.exists():
        print(f"[!] Не найдено: {description} ({path})")
        return False
    return True

def run_python(script):
    print(f"[+] Запуск: {script}")
    result = subprocess.run([sys.executable, str(script)])
    if result.returncode != 0:
        print(f"[!] Ошибка при выполнении {script}")
        sys.exit(1)

def main():
    check_all_tools()
    # Проверка наличия образа, ядра, dtb
    need_make_image = False
    if not check_file(IMG_PATH, "raspi.img"):
        need_make_image = True
    if not check_file(KERNEL_IMAGE, "Ядро Image"):
        print("[!] Сначала соберите ядро через main.py!")
        sys.exit(1)
    if not check_file(DTB_FILE, "DTB-файл"):
        print("[!] Сначала соберите ядро через main.py!")
        sys.exit(1)
    if need_make_image:
        print("[+] Создаём образ...")
        run_python(SRC_PATH / "make_image.py")
    # Проверка и запуск теста QEMU
    print("[+] Запуск теста QEMU...")
    run_python(SRC_PATH / "tests" / "test_qemu.py")
    print("[+] Всё готово! Если видите приглашение к входу или bash — образ рабочий.")

if __name__ == "__main__":
    main() 