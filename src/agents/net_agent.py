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
POLL_INTERVAL = 1.0
BRIDGE_NAME = "br0"


def run_cmd(cmd):
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error("Команда %s завершилась с ошибкой: %s", cmd, e)
        if e.stdout:
            logging.error("stdout: %s", e.stdout.strip())
        if e.stderr:
            logging.error("stderr: %s", e.stderr.strip())
        return False


def apply_system_settings(idl):
    system_table = idl.tables.get("System")
    if not system_table or not system_table.rows:
        return
    row = next(iter(system_table.rows.values()))
    if getattr(row, "hostname", None):
        run_cmd(["hostname", row.hostname])
    if getattr(row, "timezone", None):
        tz = row.timezone
        if tz:
            Path("/etc/timezone").write_text(tz + "\n")
    if getattr(row, "logging_level", None):
        level = row.logging_level.lower()
        if level in ("debug", "info", "warning", "error", "critical"):
            logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))


def ensure_bridge():
    run_cmd(["ovs-vsctl", "--may-exist", "add-br", BRIDGE_NAME])


def apply_interface(row):
    name = row.name
    ensure_bridge()
    if name != BRIDGE_NAME:
        run_cmd(["ovs-vsctl", "--may-exist", "add-port", BRIDGE_NAME, name])
        vlan = getattr(row, "vlan", None)
        if vlan is not None:
            run_cmd(["ovs-vsctl", "set", "port", name, f"tag={vlan}"])

    if getattr(row, "mtu", None):
        run_cmd(["ip", "link", "set", "dev", name, "mtu", str(row.mtu)])

    state = getattr(row, "state", None)
    if state in ("up", "down"):
        run_cmd(["ip", "link", "set", "dev", name, state])

    ip_addr = getattr(row, "ip", None)
    if ip_addr:
        run_cmd(["ip", "addr", "replace", ip_addr, "dev", name])


def apply_interfaces(idl):
    iface_table = idl.tables.get("Interface")
    if not iface_table:
        return
    for row in iface_table.rows.values():
        if not getattr(row, "name", None):
            continue
        apply_interface(row)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not Path(SCHEMA).exists():
        logging.error("Схема не найдена: %s", SCHEMA)
        sys.exit(1)

    helper = ovs.db.idl.SchemaHelper(location=SCHEMA)
    helper.register_all()
    idl = ovs.db.idl.Idl(REMOTE, helper)

    poller = ovs.poller.Poller()
    logging.info("net_agent запущен, ждём данные из OVSDB...")

    while True:
        seqno = idl.change_seqno
        idl.run()
        if idl.change_seqno != seqno:
            apply_system_settings(idl)
            apply_interfaces(idl)

        idl.wait(poller)
        poller.timer_wait(POLL_INTERVAL * 1000)
        poller.block()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
