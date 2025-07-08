# actions/call_method.py
from helper import resolve_targets

def handle_call_method(card, act, item, owner_id):
    """
    カードインスタンスの任意メソッドを呼び出し状態を変更
    """
    targets = resolve_targets(card, act, item)
    method_name = act.get("keyword", "")  # 呼び出すメソッド名
    method_value = act.get("value", 0)  # メソッドパラメータ
    events = []
    
    if not method_name:
        return []
    
    for target in targets:
        # 安全な操作のみ許可
        if method_name == "SetFaceUp":
            target["isFaceUp"] = bool(method_value)
        elif method_name == "SetLevel":
            target["level"] = int(method_value)
        elif method_name == "SetPower":
            target["power"] = int(method_value)
        elif method_name == "SetDamage":
            target["damage"] = int(method_value)
        elif method_name == "ResetStatuses":
            target["statuses"] = []
        elif method_name == "ResetTempStatuses":
            target["tempStatuses"] = []
        else:
            # 未知のメソッドは無視
            continue
        
        # メソッド呼び出しイベントを生成
        events.append({
            "type": "CallMethod",
            "payload": {
                "cardId": target["id"],
                "methodName": method_name,
                "methodValue": method_value
            }
        })
    
    return events