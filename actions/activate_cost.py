# actions/activate_cost.py
from helper import resolve_targets, add_status

def handle_activate_cost(card, act, item, owner_id):
    """
    コスト発動状態をトグル
    """
    targets = resolve_targets(card, act, item)
    activate = act.get("value", 1) == 1  # 1 = activate, 0 = deactivate
    events = []
    
    for target in targets:
        # コスト発動状態を設定
        add_status(target, "CostActivated", activate)
        
        # コストアクティブイベントを生成
        events.append({
            "type": "ActivateCost",
            "payload": {
                "cardId": target["id"],
                "activated": activate
            }
        })
    
    return events