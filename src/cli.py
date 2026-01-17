#!/usr/bin/env python3
"""
Простой CLI для работы с OVSDB-схемой system.ovsschema.
Пример: python3 cli.py set interface eth0 ip 10.0.0.2/24
"""
import argparse
import sys
from typing import Any, Dict

import ovs.db.idl

SCHEMA = "src/schema/system.ovsschema"
REMOTE = "unix:/var/run/openvswitch/db.sock"


def get_idl(remote: str, schema_path: str) -> ovs.db.idl.Idl:
    helper = ovs.db.idl.SchemaHelper(location=schema_path)
    helper.register_all()
    return ovs.db.idl.Idl(remote, helper)


def commit(idl: ovs.db.idl.Idl):
    txn = ovs.db.idl.Transaction(idl)
    status = txn.commit_block()
    if status not in (
        ovs.db.idl.Transaction.SUCCESS,
        ovs.db.idl.Transaction.UNCHANGED,
        ovs.db.idl.Transaction.INCOMPLETE,
    ):
        raise RuntimeError(f"Transaction failed: {status}")


def upsert_row(idl: ovs.db.idl.Idl, table: str, match: Dict[str, Any], updates: Dict[str, Any]):
    tbl = idl.tables.get(table)
    if not tbl:
        raise RuntimeError(f"Table {table} not found")
    row = None
    for r in tbl.rows.values():
        ok = True
        for k, v in match.items():
            if not hasattr(r, k) or getattr(r, k) != v:
                ok = False
                break
        if ok:
            row = r
            break
    txn = ovs.db.idl.Transaction(idl)
    if row is None:
        row = txn.insert(tbl)
        for k, v in match.items():
            setattr(row, k, v)
    for k, v in updates.items():
        setattr(row, k, v)
    status = txn.commit_block()
    if status not in (
        ovs.db.idl.Transaction.SUCCESS,
        ovs.db.idl.Transaction.UNCHANGED,
        ovs.db.idl.Transaction.INCOMPLETE,
    ):
        raise RuntimeError(f"Transaction failed: {status}")


def handle_set(args):
    idl = get_idl(args.remote, args.schema)
    idl.run()
    if args.resource == "interface":
        updates: Dict[str, Any] = {}
        if args.key in ("ip", "state"):
            updates[args.key] = args.value
        elif args.key in ("mtu", "vlan"):
            updates[args.key] = int(args.value)
        else:
            raise RuntimeError(f"Unknown interface field {args.key}")
        upsert_row(idl, "Interface", {"name": args.name}, updates)
    elif args.resource == "system":
        updates: Dict[str, Any] = {args.key: args.value}
        upsert_row(idl, "System", {}, updates)
    elif args.resource == "vm":
        updates: Dict[str, Any] = {}
        if args.key in ("cpu", "ram"):
            updates[args.key] = int(args.value)
        else:
            updates[args.key] = args.value
        upsert_row(idl, "VirtualMachine", {"name": args.name}, updates)
    else:
        raise RuntimeError(f"Unknown resource {args.resource}")
    print("OK")


def handle_show(args):
    idl = get_idl(args.remote, args.schema)
    idl.run()
    tbl = idl.tables.get(args.table)
    if not tbl:
        raise RuntimeError(f"Table {args.table} not found")
    for row in tbl.rows.values():
        print(row)


def build_parser():
    parser = argparse.ArgumentParser(description="OVSDB CLI wrapper")
    parser.add_argument("--remote", default=REMOTE, help="OVSDB remote (default unix socket)")
    parser.add_argument("--schema", default=SCHEMA, help="Path to ovsschema")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setp = sub.add_parser("set", help="Set values")
    setp.add_argument("resource", choices=["interface", "system", "vm"])
    setp.add_argument("name", help="Resource name (ignored for system)")
    setp.add_argument("key", help="Field name")
    setp.add_argument("value", help="Field value")
    setp.set_defaults(func=handle_set)

    showp = sub.add_parser("show", help="Show table rows")
    showp.add_argument("table", help="Table name")
    showp.set_defaults(func=handle_show)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
