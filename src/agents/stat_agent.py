#!/usr/bin/env python3
import logging
import os
import sys
import time
from pathlib import Path

import ovs.db.idl
import ovs.poller

SCHEMA = "/etc/openvswitch/system.ovsschema"
REMOTE = "unix:/var/run/openvswitch/db.sock"
INTERVAL = 1.0


def read_cpu_load():
    try:
        return os.getloadavg()[0]
    except OSError:
        return None


def read_temp():
    candidates = list(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    for path in candidates:
        try:
            val = path.read_text().strip()
            return int(val) / 1000.0
        except Exception:
            continue
    return None


def read_ram_free():
    try:
        meminfo = Path("/proc/meminfo").read_text().splitlines()
        for line in meminfo:
            if line.startswith("MemAvailable:"):
                parts = line.split()
                return int(parts[1])  # kB
    except Exception:
        return None
    return None


def update_row(idl):
    telemetry = idl.tables.get("Telemetry")
    if telemetry is None:
        return

    # Берём единственную строку или создаём новую
    row = next(iter(telemetry.rows.values()), None)
    txn = ovs.db.idl.Transaction(idl)
    if row is None:
        row = txn.insert(telemetry)

    cpu_load = read_cpu_load()
    temp = read_temp()
    ram_free = read_ram_free()

    if cpu_load is not None:
        row.cpu_load = cpu_load
    if temp is not None:
        row.temp = temp
    if ram_free is not None:
        row.ram_free = ram_free

    status = txn.commit_block()
    logging.debug("Записана Telemetry, статус транзакции: %s", status)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not Path(SCHEMA).exists():
        logging.error("Схема не найдена: %s", SCHEMA)
        sys.exit(1)

    helper = ovs.db.idl.SchemaHelper(location=SCHEMA)
    helper.register_all()
    idl = ovs.db.idl.Idl(REMOTE, helper)
    poller = ovs.poller.Poller()
    logging.info("stat_agent запущен...")

    while True:
        idl.run()
        update_row(idl)
        idl.wait(poller)
        poller.timer_wait(int(INTERVAL * 1000))
        poller.block()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
