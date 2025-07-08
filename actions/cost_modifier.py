# actions/cost_modifier.py
from helper import resolve_targets, add_status

def handle_cost_modifier(card, act, item, owner_id):
    """
    プレイコストに修正を加える
    """
    targets = resolve_targets(card, act, item)
    cost_change = int(act.get("value", 0))  # 正の数で増加、負の数で減少
    duration = int(act.get("duration", -1))  # -1 = 永続
    events = []
    
    for target in targets:
        # コスト修正を適用
        if duration == -1:
            # 永続的なコスト修正
            add_status(target, "CostModifier", cost_change)
        else:
            # 一時的なコスト修正
            current_turn = item.get("turnCount", 0)
            expire_turn = current_turn + duration
            
            temp_statuses = target.setdefault("tempStatuses", [])
            temp_statuses.append({
                "key": "CostModifier",
                "value": str(cost_change),
                "expireTurn": expire_turn
            })
        
        # コスト修正イベントを生成
        events.append({
            "type": "CostModifier",
            "payload": {
                "cardId": target["id"],
                "costChange": cost_change,
                "duration": duration
            }
        })
    
    return events