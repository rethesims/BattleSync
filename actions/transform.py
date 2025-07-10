# actions/transform.py
from helper import resolve_targets, fetch_card_masters, d

def handle_transform(card, act, item, owner_id):
    """
    カードを別のカードに変身
    selectionKey サポート追加：選択結果に基づいて変身先を決定
    """
    # Transform アクションで selectionKey が変身先を決定するために使用されている場合、
    # resolve_targets で selectionKey を使用してはいけない
    # 代わりに target パラメータを使用してターゲットを決定する
    act_for_targets = act.copy()
    if act.get("selectionKey") and act.get("target"):
        # selectionKey は変身先の決定に使用されるため、resolve_targets では無視する
        act_for_targets.pop("selectionKey", None)
    
    targets = resolve_targets(card, act_for_targets, item)
    
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
    
    # 変身先のカードマスター情報を取得
    card_masters = fetch_card_masters([transform_to])
    
    for target in targets:
        # 変身前の情報を保存
        original_id = target["baseCardId"]
        
        # 変身実行
        target["baseCardId"] = transform_to
        
        # カードマスターデータがある場合、カードの基本属性を更新
        if transform_to in card_masters:
            master_data = card_masters[transform_to]
            
            # 基本属性の更新
            if "power" in master_data:
                target["power"] = d(master_data["power"])
                target["currentPower"] = d(master_data["power"])
            
            if "damage" in master_data:
                target["damage"] = d(master_data["damage"])
                target["currentDamage"] = d(master_data["damage"])
            
            if "level" in master_data:
                target["level"] = d(master_data["level"])
                target["currentLevel"] = d(master_data["level"])
            
            # effectList を更新（新しいカードの能力を取得）
            if "effectList" in master_data:
                target["effectList"] = master_data["effectList"]
        
        # 変身時はステータスもリセット（オプション）
        if act.get("resetStatuses", False):
            target["statuses"] = []
            target["tempStatuses"] = []
        
        # power/damage のリセットや引き継ぎ処理（手動指定の場合）
        if act.get("resetPower", False):
            target["power"] = d(1000)  # デフォルト値
            target["currentPower"] = d(1000)
        if act.get("resetDamage", False):
            target["damage"] = d(0)
            target["currentDamage"] = d(0)
        
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