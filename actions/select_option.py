# actions/select_option.py
import random

def handle_select_option(card, act, item, owner_id):
    """
    クライアントが提示した選択肢から選ばせる、または重み付きランダム選択を実行する
    """
    options = act.get("options", [])
    weights = act.get("weights", [])
    prompt = act.get("prompt", "選択してください")
    selection_key = act.get("selectionKey", "option_select")
    mode = act.get("mode", "client")  # "client" または "random"
    
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
    
    # モードがrandomの場合、サーバー側で重み付きランダム選択を実行
    if mode == "random":
        # 重み付き選択の実行
        if weights and len(weights) == len(options):
            # 重みを数値に変換
            numeric_weights = [float(w) for w in weights]
            # 重み付きランダム選択を実行
            selected_value = random.choices(options, weights=numeric_weights)[0]
        else:
            # 重みが指定されていない場合は均等ランダム選択
            selected_value = random.choice(options)
        
        # 選択結果をchoiceResponsesに自動的に追加
        item.setdefault("choiceResponses", []).append({
            "requestId": selection_key,
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
    
    # 従来のクライアント側選択
    elif weights and len(weights) == len(options):
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