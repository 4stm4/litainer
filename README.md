# Litainer

Сборщик управляемого ARM64 rootfs и ядра для Raspberry Pi с транзакционной базой конфигураций (OVSDB), агентами и готовым образом `raspi.img`.

## Что внутри
- **Ядро**: сборка rpi-linux с включёнными KVM/VHOST/VFIO, iSCSI/Multipath, cgroups, watchdog.
- **Rootfs**: базовые пакеты (`bash`, `coreutils`, `curl`, `vim`, `iproute2`, `openvswitch`, `python3-ovs`, `qemu-system-aarch64`, `iscsitarget`, `socat`), копирование всех зависимостей и загрузчика, dev-ноды, fstab/hostname/passwd/group.
- **OVSDB (Sysdb)**: схема `src/schema/system.ovsschema` с таблицами System, Interface, VirtualMachine, Storage, Telemetry.
- **Агенты**: `net_agent` (сеть + OVS bridge), `storage_agent` (iSCSI), `vm_agent` (QEMU/KVM + cgroup), `stat_agent` (телеметрия), init-скрипт `rcS` монтирует `/proc`/`/sys`, запускает ovsdb-server и агентов, пингует watchdog.
- **CLI**: `src/cli.py` — простой враппер поверх ovsdb-client для управления Sysdb.
- **Образ**: `make_image.py` создаёт `raspi.img` (boot + rootfs), копирует `kernel8.img` и DTB из сборки.

## Требования
- Linux x86_64/ARM64, Python 3.8+, `sudo`.
- Утилиты: `apt-get`, `git`, `wget`, `ar`, `ldd`, `tar` с `--zstd`.
- Для сборки ядра: `build-essential libncurses-dev bison flex libssl-dev bc gpgv2`.
- Для образа/QEMU: `losetup`, `sfdisk`, `mkfs.vfat`, `mkfs.ext4`, `qemu-system-aarch64`, `iscsiadm` (часть open-iscsi).

## Быстрый старт
```bash
git clone <repo_url>
cd litainer
sudo apt-get update
sudo apt-get install -y build-essential libncurses-dev bison flex libssl-dev bc git gpgv2 \
    qemu-system-aarch64 util-linux dosfstools e2fsprogs sfdisk wget ar
sudo python3 src/main.py
```
Результат:
- `container/` — готовый rootfs с модулями ядра и OVSDB-агентами.
- `raspi.img` — образ с двумя разделами (boot/rootfs).

## Сборка внутри Docker (с пробросом каталога)
```bash
# Собрать образ окружения
docker build -t litainer-build .

# Запустить сборку, передав текущую папку внутрь контейнера
docker run --privileged --rm \
  -v "$(pwd)":/workspace \
  -w /workspace \
  litainer-build \
  bash -lc "python3 src/main.py"
```
> Нужен `--privileged` (или проброс /dev/loop* и CAP_SYS_ADMIN), чтобы dd/losetup/mknod работали при создании rootfs и raspi.img.
Артефакты (`container/`, `raspi.img`, логи) появятся в смонтированной папке хоста.

## Структура
- `src/main.py` — полный пайплайн: ядро, rootfs, агенты, образ.
- `src/adapters/` — работа с ФС, сетью, пакетами, ядром.
- `src/core/` — настройка rootfs, init-скрипт, cgroups, watchdog.
- `src/agents/` — демоны OVSDB: net/storage/vm/stat.
- `src/schema/system.ovsschema` — описание Sysdb.
- `src/tests/` — smoke и QEMU проверки.
- `src/cli.py` — CLI для Sysdb.

## Использование CLI (локально или внутри образа)
```bash
# Пример: задать IP и VLAN интерфейса
python3 src/cli.py set interface eth0 ip 10.0.0.2/24
python3 src/cli.py set interface eth0 vlan 100
# Запустить VM
python3 src/cli.py set vm vm1 state run
# Посмотреть таблицу
python3 src/cli.py show Interface
```
Параметры `--remote` и `--schema` позволяют подключаться к удалённому OVSDB (по умолчанию `unix:/var/run/openvswitch/db.sock`).

## Агенты и поведение
- `net_agent.py`: hostname/timezone/logging_level из таблицы System; создаёт OVS bridge `br0`, добавляет порты, MTU/state/IP, VLAN.
- `storage_agent.py`: логинится к target_iqn/portal_ip, ждёт LUN, монтирует на mount_point.
- `vm_agent.py`: транслирует VirtualMachine в процессы QEMU/KVM, добавляет PIDs в cgroup `vm.slice`.
- `stat_agent.py`: каждую секунду пишет Telemetry (loadavg, температура, свободная память).
- `rcS`: монтирует `/proc`/`/sys`, поднимает cgroup, запускает ovsdb-server с `system.ovsschema`, агенты и watchdog tick.

## Тесты/валидация
- Статические проверки: `python3 src/tests/test_smoke.py` (sudo для chroot) — ldd /bin/bash в контейнере, наличие базовых .so, `ovsdb-tool check-schema`.
- QEMU smoke: `python3 src/tests/test_qemu.py` — запускает `raspi.img` в QEMU с port-forward 6640, ждёт маркеры старта агентов и проверяет TCP-доступность ovsdb-server.

## Примечания
- Сборка требует sudo (mknod, apt, losetup). `tar` должен поддерживать `--zstd` для .deb с `data.tar.zst`.
- Для ARM64 оптимальнее собирать на той же архитектуре или с эмуляцией.
- Пакеты для rootfs подтягиваются через `apt-get download`, затем распаковываются в `container/`.
