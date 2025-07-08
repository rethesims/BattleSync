# actions/set_status.py
from helper import resolve_targets, add_status, add_temp_status

def handle_set_status(card, act, item, owner_id):
    """
    任意のステータスを対象カードに付与
    """
    targets = resolve_targets(card, act, item)
    status_key = act.get("keyword", "Status")
    status_value = act.get("value", 1)
    duration = int(act.get("duration", -1))  # -1 = 永続
    events = []
    
    for target in targets:
        # ステータスを設定
        if duration == -1:
            # 永続ステータス
            add_status(target, status_key, status_value)
        else:
            # 一時ステータス
            current_turn = item.get("turnCount", 0)
            expire_turn = current_turn + duration
            add_temp_status(target, status_key, status_value, expire_turn)
        
        # ステータス設定イベントを生成
        events.append({
            "type": "SetStatus",
            "payload": {
                "cardId": target["id"],
                "statusKey": status_key,
                "statusValue": status_value,
                "duration": duration
            }
        })
    
    return events