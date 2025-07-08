# actions/counter_change.py
from helper import resolve_targets, add_status

def handle_counter_change(card, act, item, owner_id):
    """
    カウンター値を増減する
    """
    targets = resolve_targets(card, act, item)
    counter_type = act.get("keyword", "Counter")  # Counter, Token, etc.
    change_value = int(act.get("value", 1))
    events = []
    
    for target in targets:
        # 現在のカウンター値を取得
        counter_key = f"{counter_type}Count"
        current_count = 0
        
        # 既存のカウンターを取得
        for status in target.get("statuses", []):
            if status["key"] == counter_key:
                current_count = int(status["value"])
                break
        
        # カウンターを変更
        new_count = max(0, current_count + change_value)  # 0未満にはならない
        add_status(target, counter_key, new_count)
        
        # カウンター変更イベントを生成
        events.append({
            "type": "CounterChange",
            "payload": {
                "cardId": target["id"],
                "counterType": counter_type,
                "changeValue": change_value,
                "newCount": new_count
            }
        })
    
    return events