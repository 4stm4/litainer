#!/usr/bin/env python3
import logging
import subprocess
import sys
import time
from pathlib import Path

import ovs.db.idl
import ovs.poller

SCHEMA = "/etc/openvswitch/system.ovsschema"
REMOTE = "unix:/var/run/openvswitch/db.sock"
POLL_INTERVAL = 2.0


def run_cmd(cmd):
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error("Команда %s завершилась ошибкой: %s", cmd, e)
        if e.stdout:
            logging.error("stdout: %s", e.stdout.strip())
        if e.stderr:
            logging.error("stderr: %s", e.stderr.strip())
        return False


def ensure_session(row):
    target = row.target_iqn
    portal = row.portal_ip
    lun = getattr(row, "lun", None)
    mount_point = getattr(row, "mount_point", "") or f"/mnt/{target.replace(':', '_')}"

    if not target or not portal:
        logging.error("Строка Storage не содержит target_iqn или portal_ip")
        return

    # Логин в iSCSI
    login_cmd = ["iscsiadm", "-m", "node", "-T", target, "-p", portal, "--login"]
    run_cmd(login_cmd)

    device_path = f"/dev/disk/by-path/ip-{portal}:3260-iscsi-{target}-lun-{lun or 0}"

    # Ожидаем появления устройства
    for _ in range(5):
        if Path(device_path).exists():
            break
        time.sleep(1)

    if not Path(device_path).exists():
        logging.error("Устройство не появилось: %s", device_path)
        return

    # Монтируем
    Path(mount_point).mkdir(parents=True, exist_ok=True)
    # Проверим, уже смонтировано ли
    already = subprocess.run(["findmnt", "-n", "-o", "TARGET", "--target", device_path], capture_output=True, text=True)
    if already.returncode == 0 and mount_point in already.stdout:
        logging.info("Уже смонтировано: %s -> %s", device_path, mount_point)
        return

    run_cmd(["mount", device_path, mount_point])
    logging.info("Смонтировано: %s -> %s", device_path, mount_point)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not Path(SCHEMA).exists():
        logging.error("Схема не найдена: %s", SCHEMA)
        sys.exit(1)

    helper = ovs.db.idl.SchemaHelper(location=SCHEMA)
    helper.register_all()
    idl = ovs.db.idl.Idl(REMOTE, helper)

    poller = ovs.poller.Poller()
    logging.info("storage_agent запущен...")

    while True:
        seqno = idl.change_seqno
        idl.run()
        if idl.change_seqno != seqno:
            storage_table = idl.tables.get("Storage")
            if storage_table:
                for row in storage_table.rows.values():
                    ensure_session(row)

        idl.wait(poller)
        poller.timer_wait(POLL_INTERVAL * 1000)
        poller.block()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
