import unittest
import os
import sys

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from hospital_cli import parse_args


class TestHospitalCliArgs(unittest.TestCase):
    def test_strict_hospital_subcommand_order(self):
        # Strict format: hospital <hospital_code> <subcommand> [args...]
        args = parse_args(["femh", "dept", "家醫"])
        self.assertEqual(args.hospital, "femh")
        self.assertEqual(args.subcommand, "dept")
        self.assertEqual(args.keyword, "家醫")

    def test_invalid_reversed_order_rejected(self):
        # Reversed format (hospital dept femh) must raise or result in invalid hospital/subcommand
        with self.assertRaises(SystemExit):
            parse_args(["dept", "femh", "家醫"])

    def test_cgmh_schedule(self):
        args = parse_args(["cgmh", "schedule", "V1200A", "林士驊", "-b", "V"])
        self.assertEqual(args.hospital, "cgmh")
        self.assertEqual(args.subcommand, "schedule")
        self.assertEqual(args.dept, "V1200A")
        self.assertEqual(args.doctor, "林士驊")
        self.assertEqual(args.branch, "V")

    def test_tpech_progress(self):
        args = parse_args(["tpech", "progress", "家醫", "-b", "H"])
        self.assertEqual(args.hospital, "tpech")
        self.assertEqual(args.subcommand, "progress")
        self.assertEqual(args.dept, "家醫")
        self.assertEqual(args.branch, "H")

    def test_cgmh_records(self):
        args = parse_args(["cgmh", "records", "A123456789", "800101"])
        self.assertEqual(args.hospital, "cgmh")
        self.assertEqual(args.subcommand, "records")
        self.assertEqual(args.id_number, "A123456789")
        self.assertEqual(args.birthday, "800101")


if __name__ == "__main__":
    unittest.main()
