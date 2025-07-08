# actions/summon.py
from helper import resolve_targets

def handle_summon(card, act, item, owner_id):
    """
    手札からフィールドへの召喚処理
    """
    targets = resolve_targets(card, act, item)
    events = []
    
    for target in targets:
        # 手札にあるカードのみ召喚可能
        if target.get("zone") != "Hand":
            continue
            
        # 召喚者のカードのみ召喚可能
        if target.get("ownerId") != owner_id:
            continue
            
        from_zone = target.get("zone")
        target["zone"] = "Field"
        
        # 召喚イベントを生成
        events.append({
            "type": "Summon",
            "payload": {
                "cardId": target["id"],
                "fromZone": from_zone,
                "toZone": "Field",
                "ownerId": owner_id
            }
        })
    
    return events