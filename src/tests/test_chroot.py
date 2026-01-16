import subprocess
from pathlib import Path
import sys

ROOTFS_PATH = Path(__file__).parent.parent.parent / "container"

def test_container_chroot(rootfs_path):
    try:
        result = subprocess.run([
            "sudo", "chroot", str(rootfs_path), "/bin/bash", "-c", "echo ok"
        ], capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if output == "ok":
            print("Тест chroot: УСПЕХ — контейнер рабочий!")
            return True
        else:
            print(f"Тест chroot: ОШИБКА — неожиданный вывод: {output}")
            return False
    except Exception as e:
        print(f"Тест chroot: ОШИБКА — {e}")
        return False

if __name__ == "__main__":
    success = test_container_chroot(ROOTFS_PATH)
    sys.exit(0 if success else 1) 