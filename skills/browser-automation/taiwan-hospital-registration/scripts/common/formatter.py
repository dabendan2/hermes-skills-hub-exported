import json

def print_result(result: dict, is_json: bool = False, header: str = "SUCCESS"):
    """
    Standardized printer for hospital CLI results.
    """
    if is_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not result.get("success", False):
        print(f"\n=== {header}_FAILURE ===")
        print(f"錯誤訊息：{result.get('error', '未知錯誤')}")
        print("====================")
        return

    print(f"\n=== {header}_SUCCESS ===")
    for k, v in result.items():
        if k in ("success", "count", "error"):
            continue
        if isinstance(v, list):
            print(f"{k} ({len(v)} 項):")
            for idx, item in enumerate(v, 1):
                if isinstance(item, dict):
                    fields = " | ".join(f"{ik}: {iv}" for ik, iv in item.items())
                    print(f"  {idx}. {fields}")
                else:
                    print(f"  {idx}. {item}")
        elif isinstance(v, dict):
            print(f"{k}:")
            for ik, iv in v.items():
                print(f"  • {ik}: {iv}")
        else:
            print(f"{k}: {v}")
    print("====================")
