# actions/select_option.py
from helper import weighted_random_select

def handle_select_option(card, act, item, owner_id):
    """
    サーバー側で重み付きランダム選択を実行し、choiceResponses に自動追加
    """
    options = act.get("options", [])
    weights = act.get("weights", [])
    prompt = act.get("prompt", "選択してください")
    selection_key = act.get("selectionKey", "option_select")
    mode = act.get("mode", "client")  # "random" でサーバー側選択、"client" でクライアント側選択
    
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
    
    # サーバー側ランダム選択モード
    if mode == "random":
        # 重み付きランダム選択を実行
        if weights and len(weights) == len(options):
            # 重みを整数に変換
            weight_values = [int(w) for w in weights]
            selected_value = weighted_random_select(options, weight_values)
        else:
            # 重みが指定されていない場合は均等選択
            selected_value = options[0] if len(options) == 1 else weighted_random_select(options, [1] * len(options))
        
        # choiceResponses に自動追加
        item.setdefault("choiceResponses", []).append({
            "requestId": selection_key,
            "playerId": owner_id,
            "selectedValue": selected_value
        })
        
        return [{
            "type": "SelectOption",
            "payload": {
                "selectionKey": selection_key,
                "selectedValue": selected_value,
                "prompt": prompt
            }
        }]
    
    # クライアント側選択モード（従来通り）
    else:
        # 重みが指定されている場合は重み付き選択
        if weights and len(weights) == len(options):
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