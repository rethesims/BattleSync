# actions/transform.py
from helper import resolve_targets

def handle_transform(card, act, item, owner_id):
    """
    カードを別のカードに変身
    """
    targets = resolve_targets(card, act, item)
    transform_to = act.get("keyword", "")  # 変身先のカードID
    events = []
    
    if not transform_to:
        return []
    
    for target in targets:
        # 変身前の情報を保存
        original_id = target["baseCardId"]
        
        # 変身実行
        target["baseCardId"] = transform_to
        
        # 変身時はステータスもリセット（オプション）
        if act.get("resetStatuses", False):
            target["statuses"] = []
            target["tempStatuses"] = []
        
        # 変身イベントを生成
        events.append({
            "type": "Transform",
            "payload": {
                "cardId": target["id"],
                "fromCardId": original_id,
                "toCardId": transform_to,
                "resetStatuses": act.get("resetStatuses", False)
            }
        })
    
    return events