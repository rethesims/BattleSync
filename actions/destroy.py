# actions/destroy.py
from helper import resolve_targets

def handle_destroy(card, act, item, owner_id):
    """
    指定したカードを破壊し墓地へ移動する
    """
    targets = resolve_targets(card, act, item)
    events = []
    
    for target in targets:
        # 既に墓地にある場合はスキップ
        if target.get("zone") == "Graveyard":
            continue
            
        from_zone = target.get("zone")
        target["zone"] = "Graveyard"
        
        # 破壊イベントを生成
        events.append({
            "type": "Destroy",
            "payload": {
                "cardId": target["id"],
                "fromZone": from_zone,
                "toZone": "Graveyard"
            }
        })
    
    return events