# actions/transform.py
from helper import resolve_targets

def handle_transform(card, act, item, owner_id):
    """
    カードを別のカードに変身
    """
    targets = resolve_targets(card, act, item)
    events = []
    
    # 変身先を決定（selectionKeyが指定されている場合は選択結果を使用）
    transform_to = None
    selection_key = act.get("selectionKey")
    
    if selection_key:
        # choiceResponsesから選択結果を取得
        responses = item.get("choiceResponses", [])
        resp = next((r for r in responses if r.get("requestId") == selection_key), None)
        if resp:
            transform_to = resp.get("selectedValue")
    
    # selectionKeyが指定されていない場合はkeywordを使用
    if not transform_to:
        transform_to = act.get("keyword", "")
    
    # transformOptionsが指定されている場合、そちらを優先
    if act.get("transformOptions"):
        transform_options = act.get("transformOptions", [])
        if transform_options and selection_key:
            # 選択結果がtransformOptionsのindexを指している場合
            if resp and resp.get("selectedValue") in transform_options:
                transform_to = resp.get("selectedValue")
    
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