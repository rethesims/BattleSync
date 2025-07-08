# actions/select.py
from helper import resolve_targets

def handle_select(card, act, item, owner_id):
    """
    フィールド上のカードを選択する
    選択されたカードのIDを selectionKey に保存し、後続のアクションで参照できるようにする
    """
    # 選択対象を取得
    targets = resolve_targets(card, act, item)
    
    # 選択モードの確認
    mode = act.get("mode", "single")  # single, multiple, all
    max_select = act.get("value", 1)  # 最大選択数
    
    # 選択肢がない場合は空のイベントを返す
    if not targets:
        return [{
            "type": "Select",
            "payload": {
                "selectionKey": act.get("selectionKey", "default"),
                "selectedIds": [],
                "prompt": act.get("prompt", "選択するカードがありません")
            }
        }]
    
    # 選択肢を制限
    if mode == "single":
        max_select = 1
    elif mode == "all":
        max_select = len(targets)
    
    # 実際の選択数を制限
    available_count = min(len(targets), max_select)
    
    # SendChoiceRequest イベントを生成してクライアントに選択肢を提示
    return [{
        "type": "SendChoiceRequest",
        "payload": {
            "requestId": act.get("selectionKey", "default"),
            "playerId": owner_id,
            "promptText": act.get("prompt", f"カードを選択してください（最大{available_count}枚）"),
            "options": [t["id"] for t in targets],
            "maxSelect": available_count,
            "mode": mode
        }
    }]