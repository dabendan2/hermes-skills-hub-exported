import os

def get_user_credentials():
    """
    Load credentials strictly from USER_* environment variables or ~/.hermes/.env.
    DAD_* variables are explicitly IGNORED.
    """
    creds = {
        "name": os.environ.get("USER_NAME", ""),
        "id_number": os.environ.get("USER_ID_NUMBER", "") or os.environ.get("USER_ID", ""),
        "birthday_roc": os.environ.get("USER_BIRTHDAY_ROC", "") or os.environ.get("USER_BIRTHDAY", ""),
        "birthday_ad": os.environ.get("USER_BIRTHDAY_AD", "")
    }

    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("USER_") and "=" in line:
                        k, v = line.split("=", 1)
                        clean_v = v.strip().strip('"').strip("'")
                        field_name = k.replace("USER_", "").lower()
                        if field_name == "name" and not creds["name"]:
                            creds["name"] = clean_v
                        elif field_name in ("id_number", "id") and not creds["id_number"]:
                            creds["id_number"] = clean_v
                        elif field_name in ("birthday_roc", "birthday") and not creds["birthday_roc"]:
                            creds["birthday_roc"] = clean_v
                        elif field_name == "birthday_ad" and not creds["birthday_ad"]:
                            creds["birthday_ad"] = clean_v
        except Exception:
            pass

    return creds
