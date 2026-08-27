import unittest
import os
import sys
from unittest.mock import patch, MagicMock

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from modules.femh import FemhModule
from modules.tpech import TpechModule
from modules.cgmh import CgmhModule


class TestHospitalModules(unittest.TestCase):
    def test_femh_dept_search(self):
        mod = FemhModule()
        res = mod.dept(keyword="家醫")
        self.assertTrue(res["success"])
        self.assertGreater(res["count"], 0)
        self.assertTrue(any("家庭醫學" in d["department_name"] for d in res["departments"]))

    def test_tpech_dept_search(self):
        mod = TpechModule()
        res = mod.dept(keyword="家醫")
        self.assertTrue(res["success"])
        self.assertGreater(res["count"], 0)

    def test_cgmh_dept_search(self):
        mod = CgmhModule()
        res = mod.dept(keyword="耳鼻喉")
        self.assertTrue(res["success"])
        self.assertGreater(res["count"], 0)


if __name__ == "__main__":
    unittest.main()
