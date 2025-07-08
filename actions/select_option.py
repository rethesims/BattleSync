# actions/select_option.py

def handle_select_option(card, act, item, owner_id):
    """
    クライアントが提示した選択肢から選ばせる
    """
    options = act.get("options", [])
    weights = act.get("weights", [])
    prompt = act.get("prompt", "選択してください")
    selection_key = act.get("selectionKey", "option_select")
    
    # 選択肢が空の場合
    if not options:
        return [{
            "type": "SelectOption",
            "payload": {
                "selectionKey": selection_key,
                "selectedOption": None,
                "prompt": "選択肢がありません"
            }
        }]
    
    # 重みが指定されている場合は重み付き選択
    if weights and len(weights) == len(options):
        # 重み付き選択の場合、クライアント側で処理
        return [{
            "type": "SelectOption",
            "payload": {
                "selectionKey": selection_key,
                "options": options,
                "weights": weights,
                "prompt": prompt
            }
        }]
    else:
        # 通常の選択
        return [{
            "type": "SelectOption",
            "payload": {
                "selectionKey": selection_key,
                "options": options,
                "prompt": prompt
            }
        }]