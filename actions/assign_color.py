# actions/assign_color.py
from helper import resolve_targets, add_status

def handle_assign_color(card, act, item, owner_id):
    """
    カラーコストを付与する
    """
    targets = resolve_targets(card, act, item)
    color = act.get("keyword", "Red")  # Red, Blue, Green, Yellow, etc.
    value = int(act.get("value", 1))
    events = []
    
    for target in targets:
        # カラーコストを付与
        color_key = f"ColorCost_{color}"
        current_cost = 0
        
        # 既存のカラーコストを取得
        for status in target.get("statuses", []):
            if status["key"] == color_key:
                current_cost = int(status["value"])
                break
        
        # カラーコストを追加
        new_cost = current_cost + value
        add_status(target, color_key, new_cost)
        
        # カラー付与イベントを生成
        events.append({
            "type": "AssignColor",
            "payload": {
                "cardId": target["id"],
                "color": color,
                "value": value,
                "totalCost": new_cost
            }
        })
    
    return events