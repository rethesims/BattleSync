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
    
    # 選択イベントを生成
    return [{
        "type": "Select",
        "payload": {
            "selectionKey": act.get("selectionKey", "default"),
            "availableIds": [t["id"] for t in targets],
            "maxSelect": available_count,
            "prompt": act.get("prompt", f"カードを選択してください（最大{available_count}枚）")
        }
    }]