# actions/gain_level.py
from helper import resolve_targets

def handle_gain_level(card, act, item, owner_id):
    """
    カードのレベルを一時的に上げる
    """
    targets = resolve_targets(card, act, item)
    level_boost = int(act.get("value", 1))
    events = []
    
    for target in targets:
        # 現在のレベルを取得
        current_level = target.get("level", 0)
        
        # レベルを上げる
        target["level"] = current_level + level_boost
        
        # レベルブーストイベントを生成
        events.append({
            "type": "GainLevel",
            "payload": {
                "cardId": target["id"],
                "levelBoost": level_boost,
                "newLevel": target["level"]
            }
        })
    
    return events