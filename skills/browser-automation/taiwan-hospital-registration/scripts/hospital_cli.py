#!/usr/bin/env python3
"""
Taiwan Hospital Registration Unified CLI (`hospital`)
Single entrypoint tool for Taiwan hospital registrations, schedules, and live progress.

Strict Usage Syntax:
  hospital <hospital_code> <subcommand> [args...] [flags]

Valid hospital_code: cgmh, femh, tpech, heping
Valid subcommand: dept, schedule, progress, records, book, cancel
"""

import sys
import os
import argparse
import json

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from common.formatter import print_result
from modules.cgmh import CgmhModule
from modules.femh import FemhModule
from modules.tpech import TpechModule

HOSPITAL_MAP = {
    "cgmh": CgmhModule,
    "femh": FemhModule,
    "tpech": TpechModule,
    "heping": TpechModule
}

VALID_SUBCOMMANDS = {
    "dept": "dept", "depts": "dept", "d": "dept",
    "schedule": "schedule", "s": "schedule", "doctor": "schedule",
    "progress": "progress", "p": "progress",
    "records": "records", "query": "records", "r": "records",
    "book": "book", "b": "book",
    "cancel": "cancel", "c": "cancel"
}

def parse_args(args_list=None):
    if args_list is None:
        args_list = sys.argv[1:]

    if not args_list:
        print("Usage: hospital <hospital_code> <subcommand> [args...] [flags]")
        print("Supported hospital_code: cgmh, femh, tpech")
        print("Supported subcommands: dept, schedule, progress, records, book, cancel")
        sys.exit(1)

    hospital_input = args_list[0].lower()
    if hospital_input not in HOSPITAL_MAP:
        print(f"Error: 嚴格指令格式為 'hospital <hospital_code> <subcommand>'。'{hospital_input}' 不是合法的 hospital_code (請使用 cgmh, femh, tpech)。", file=sys.stderr)
        sys.exit(1)

    hospital = hospital_input
    remaining = args_list[1:]

    if not remaining:
        print(f"Usage: hospital {hospital} <subcommand> [args...] [flags]")
        print("Subcommands: dept, schedule, progress, records, book, cancel")
        sys.exit(1)

    raw_subcommand = remaining[0].lower()
    subcommand = VALID_SUBCOMMANDS.get(raw_subcommand, "")

    if not subcommand:
        print(f"Error: 不支援的子命令 '{raw_subcommand}'。合法子命令包含: dept, schedule, progress, records, book, cancel", file=sys.stderr)
        sys.exit(1)

    cleaned_args = remaining[1:]

    parsed = argparse.Namespace()
    parsed.hospital = hospital
    parsed.subcommand = subcommand
    parsed.json = "--json" in args_list
    parsed.keyword = ""
    parsed.dept = ""
    parsed.doctor = ""
    parsed.session = ""
    parsed.room = ""
    parsed.number = ""
    parsed.id_number = ""
    parsed.birthday = ""
    parsed.branch = ""
    parsed.date = ""

    # Filter out option flags and their values
    positionals = []
    skip_next = False
    for i, arg in enumerate(cleaned_args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("--branch", "-b"):
            if i + 1 < len(cleaned_args):
                parsed.branch = cleaned_args[i + 1]
                skip_next = True
        elif arg.startswith("-b="):
            parsed.branch = arg.split("=", 1)[1]
        elif arg == "--week":
            if i + 1 < len(cleaned_args):
                skip_next = True
        elif arg.startswith("--week="):
            pass
        elif arg == "--json":
            pass
        elif not arg.startswith("-"):
            positionals.append(arg)

    if subcommand == "dept":
        if positionals:
            parsed.keyword = positionals[0]
    elif subcommand == "schedule":
        if positionals:
            parsed.dept = positionals[0]
        if len(positionals) > 1:
            parsed.doctor = positionals[1]
    elif subcommand == "progress":
        if positionals:
            parsed.dept = positionals[0]
        if len(positionals) > 1:
            parsed.doctor = positionals[1]
        if len(positionals) > 2:
            parsed.session = positionals[2]
        if len(positionals) > 3:
            parsed.room = positionals[3]
        if len(positionals) > 4:
            parsed.number = positionals[4]
    elif subcommand == "records":
        if positionals:
            parsed.id_number = positionals[0]
        if len(positionals) > 1:
            parsed.birthday = positionals[1]
    elif subcommand in ("book", "cancel"):
        if positionals:
            parsed.id_number = positionals[0]
        if len(positionals) > 1:
            parsed.birthday = positionals[1]

    return parsed

def main():
    args = parse_args()

    module_cls = HOSPITAL_MAP.get(args.hospital)
    if not module_cls:
        print_result({"success": False, "error": f"不支援的醫院代碼：「{args.hospital}」"}, is_json=args.json)
        sys.exit(1)

    module = module_cls()

    if args.subcommand == "dept":
        res = module.dept(keyword=args.keyword, branch=args.branch)
        print_result(res, is_json=args.json, header="DEPT")
    elif args.subcommand == "schedule":
        res = module.schedule(dept=args.dept, doctor=args.doctor, branch=args.branch)
        print_result(res, is_json=args.json, header="SCHEDULE")
    elif args.subcommand == "progress":
        res = module.progress(dept=args.dept, doctor=args.doctor, session=args.session, room=args.room, number=args.number, branch=args.branch)
        print_result(res, is_json=args.json, header="PROGRESS")
    elif args.subcommand == "records":
        res = module.records(id_number=args.id_number, birthday=args.birthday, branch=args.branch)
        print_result(res, is_json=args.json, header="QUERY")
    elif args.subcommand == "book" and hasattr(module, "book"):
        res = module.book(id_number=args.id_number, birthday=args.birthday, branch=args.branch)
        print_result(res, is_json=args.json, header="BOOK")
    elif args.subcommand == "cancel" and hasattr(module, "cancel"):
        res = module.cancel(id_number=args.id_number, birthday=args.birthday, branch=args.branch)
        print_result(res, is_json=args.json, header="CANCEL")

if __name__ == "__main__":
    main()
