import unittest
import os
import sys
from unittest.mock import patch, mock_open

# Add scripts directory to path for testing
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from common.env import get_user_credentials


class TestEnvCredentials(unittest.TestCase):
    def setUp(self):
        # Save env vars
        self._orig_env = os.environ.copy()

    def tearDown(self):
        # Restore env vars
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_get_user_credentials_from_env(self):
        os.environ["USER_NAME"] = "Test User"
        os.environ["USER_ID_NUMBER"] = "A123456789"
        os.environ["USER_BIRTHDAY_ROC"] = "800101"
        os.environ["USER_BIRTHDAY_AD"] = "19910101"

        # Set DAD variables as well
        os.environ["DAD_NAME"] = "Dad Name"
        os.environ["DAD_ID_NUMBER"] = "B987654321"

        creds = get_user_credentials()

        self.assertEqual(creds["name"], "Test User")
        self.assertEqual(creds["id_number"], "A123456789")
        self.assertEqual(creds["birthday_roc"], "800101")
        self.assertEqual(creds["birthday_ad"], "19910101")

        # Must NOT match DAD credentials
        self.assertNotEqual(creds["name"], "Dad Name")
        self.assertNotEqual(creds["id_number"], "B987654321")

    def test_dad_env_vars_strictly_ignored(self):
        # Set ONLY DAD env vars
        os.environ.pop("USER_NAME", None)
        os.environ.pop("USER_ID_NUMBER", None)
        os.environ.pop("USER_BIRTHDAY_ROC", None)
        os.environ.pop("USER_BIRTHDAY_AD", None)

        os.environ["DAD_NAME"] = "Dad Name"
        os.environ["DAD_ID_NUMBER"] = "B987654321"
        os.environ["DAD_BIRTHDAY_ROC"] = "500505"

        with patch("builtins.open", mock_open(read_data="DAD_NAME=Dad File\nDAD_ID_NUMBER=B987654321\n")):
            creds = get_user_credentials()

        # Should NOT pick up DAD credentials at all
        self.assertEqual(creds["name"], "")
        self.assertEqual(creds["id_number"], "")
        self.assertEqual(creds["birthday_roc"], "")


if __name__ == "__main__":
    unittest.main()
