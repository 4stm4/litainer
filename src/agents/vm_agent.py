#!/usr/bin/env python3
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import ovs.db.idl
import ovs.poller

SCHEMA = "/etc/openvswitch/system.ovsschema"
REMOTE = "unix:/var/run/openvswitch/db.sock"
POLL_INTERVAL = 2.0
QEMU_CMD = os.environ.get("QEMU_BIN", "qemu-system-aarch64")
CGROUP_VM = Path("/sys/fs/cgroup/vm.slice/cgroup.procs")


class VMManager:
    def __init__(self):
        self.processes: dict[str, subprocess.Popen] = {}

    def is_running(self, name: str) -> bool:
        proc = self.processes.get(name)
        return proc is not None and proc.poll() is None

    def stop_vm(self, name: str):
        proc = self.processes.get(name)
        if proc and proc.poll() is None:
            logging.info("Останавливаем VM %s", name)
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logging.warning("VM %s не завершилась, посылаем SIGKILL", name)
                proc.kill()
            self.processes.pop(name, None)

    def start_vm(self, row):
        name = row.name
        cpu = getattr(row, "cpu", None) or 1
        ram = getattr(row, "ram", None) or 512
        disk = getattr(row, "disk_path", None)
        passthrough = getattr(row, "pci_passthrough", [])

        if not disk:
            logging.error("VM %s не имеет disk_path", name)
            return

        if self.is_running(name):
            logging.info("VM %s уже запущена", name)
            return

        args = [
            QEMU_CMD,
            "-name", name,
            "-m", str(ram),
            "-smp", str(cpu),
            "-drive", f"file={disk},if=virtio,format=raw",
            "-nographic",
            "-enable-kvm",
        ]
        for dev in passthrough:
            args += ["-device", "vfio-pci,host=" + dev]

        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.processes[name] = proc
            logging.info("Запущена VM %s (pid %s)", name, proc.pid)
            self._assign_cgroup(proc.pid)
        except Exception as e:
            logging.error("Не удалось запустить VM %s: %s", name, e)

    def _assign_cgroup(self, pid: int):
        if CGROUP_VM.exists():
            try:
                CGROUP_VM.write_text(str(pid))
            except Exception as e:
                logging.warning("Не удалось добавить pid %s в cgroup: %s", pid, e)

    def sync(self, table):
        # Создать список активных имён из таблицы
        desired = {row.name: row for row in table.rows.values() if getattr(row, "name", None)}

        # Остановить отсутствующие/stop
        for name in list(self.processes.keys()):
            row = desired.get(name)
            if not row or getattr(row, "state", "").lower() == "stop":
                self.stop_vm(name)

        # Запустить требуемые
        for name, row in desired.items():
            if getattr(row, "state", "").lower() == "run":
                self.start_vm(row)
            elif getattr(row, "state", "").lower() == "stop":
                self.stop_vm(name)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not Path(SCHEMA).exists():
        logging.error("Схема не найдена: %s", SCHEMA)
        sys.exit(1)

    helper = ovs.db.idl.SchemaHelper(location=SCHEMA)
    helper.register_all()
    idl = ovs.db.idl.Idl(REMOTE, helper)

    poller = ovs.poller.Poller()
    manager = VMManager()
    logging.info("vm_agent запущен...")

    while True:
        seqno = idl.change_seqno
        idl.run()
        if idl.change_seqno != seqno:
            vm_table = idl.tables.get("VirtualMachine")
            if vm_table:
                manager.sync(vm_table)

        idl.wait(poller)
        poller.timer_wait(POLL_INTERVAL * 1000)
        poller.block()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
