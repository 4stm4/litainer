import os
import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
ROOTFS_PATH = PROJECT_ROOT / "container"
SCHEMA_PATH = PROJECT_ROOT / "src" / "schema" / "system.ovsschema"
REQUIRED_LIBS = [
    "ld-linux-aarch64.so.1",
    "libc.so.6",
    "libpthread.so.0",
    "libnss_dns.so.2",
    "libnss_files.so.2",
    "libresolv.so.2",
]


def run_cmd(cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_chroot_ldd():
    if not ROOTFS_PATH.exists():
        print(f"[chroot-ldd] rootfs не найден: {ROOTFS_PATH}")
        return False
    ldd_path = ROOTFS_PATH / "usr" / "bin" / "ldd"
    if not ldd_path.exists():
        print(f"[chroot-ldd] ldd отсутствует в rootfs: {ldd_path}")
        return False
    try:
        result = run_cmd(["sudo", "chroot", str(ROOTFS_PATH), "/usr/bin/ldd", "/bin/bash"])
    except Exception as e:
        print(f"[chroot-ldd] ошибка запуска: {e}")
        return False

    output = result.stdout + result.stderr
    if result.returncode != 0:
        print(f"[chroot-ldd] ldd вернул {result.returncode}\n{output}")
        return False

    if "not found" in output.lower():
        print(f"[chroot-ldd] обнаружены отсутствующие библиотеки:\n{output}")
        return False

    print("[chroot-ldd] OK — зависимости /bin/bash удовлетворены.")
    return True


def check_required_libs():
    ok = True
    for lib in REQUIRED_LIBS:
        found = list(ROOTFS_PATH.rglob(lib))
        if not found:
            print(f"[libs] Не найдена библиотека {lib} в {ROOTFS_PATH}")
            ok = False
    if ok:
        print("[libs] OK — базовые библиотеки присутствуют.")
    return ok


def check_schema():
    if not SCHEMA_PATH.exists():
        print(f"[schema] схема не найдена: {SCHEMA_PATH}")
        return False
    if not shutil.which("ovsdb-tool"):
        print("[schema] ovsdb-tool не найден в PATH")
        return False
    try:
        result = run_cmd(["ovsdb-tool", "check-schema", str(SCHEMA_PATH)])
    except Exception as e:
        print(f"[schema] ошибка запуска ovsdb-tool: {e}")
        return False

    if result.returncode != 0:
        print(f"[schema] check-schema вернул {result.returncode}\n{result.stdout}{result.stderr}")
        return False

    print("[schema] OK — схема прошла проверку.")
    return True


def main():
    ok = True
    if not check_chroot_ldd():
        ok = False
    if not check_required_libs():
        ok = False
    if not check_schema():
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
