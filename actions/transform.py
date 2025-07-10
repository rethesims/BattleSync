# actions/transform.py
from helper import resolve_targets

def handle_transform(card, act, item, owner_id):
    """
    カードを別のカードに変身
    selectionKey サポート追加：選択結果に基づいて変身先を決定
    """
    # selectionKey が指定されていて target が空の場合、Self をデフォルトとする
    if act.get("selectionKey") and not act.get("target"):
        act = {**act, "target": "Self"}
    
    targets = resolve_targets(card, act, item)
    
    # 変身先の決定
    transform_to = ""
    
    # 1. selectionKey が指定されている場合、choiceResponses から取得
    selection_key = act.get("selectionKey")
    if selection_key:
        responses = item.get("choiceResponses", [])
        resp = next((r for r in responses if r.get("requestId") == selection_key), None)
        if resp:
            transform_to = resp.get("selectedValue", "")
    
    # 2. keyword パラメータ（従来通り）
    if not transform_to:
        transform_to = act.get("keyword", "")
    
    # 3. transformTo パラメータ（直接指定）
    if not transform_to:
        transform_to = act.get("transformTo", "")
    
    # 4. options から選択（transformOptions配列）
    if not transform_to:
        options = act.get("options", [])
        if options:
            transform_to = options[0]  # 最初の選択肢をデフォルト
    
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
        
        # power/damage のリセットや引き継ぎ処理
        if act.get("resetPower", False):
            target["power"] = 1000  # デフォルト値
        if act.get("resetDamage", False):
            target["damage"] = 0
        
        # 変身イベントを生成
        events.append({
            "type": "Transform",
            "payload": {
                "cardId": target["id"],
                "fromCardId": original_id,
                "toCardId": transform_to,
                "resetStatuses": act.get("resetStatuses", False),
                "resetPower": act.get("resetPower", False),
                "resetDamage": act.get("resetDamage", False)
            }
        })
    
    return events