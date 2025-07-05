### actions/move_zone.py
from helper import resolve_targets

def handle_move_zone(card, act, item, owner_id):
    """
    汎用カード移動ハンドラ
    act に `toZone` が含まれていることを前提とする。
    src: 発動元カード情報
    act: アクション定義 (type, ..., toZone)
    item: マッチ全体の状態
    owner_id: アクション発動プレイヤー
    """
    to_zone = act.get("toZone")
    # resolve_targets を使って対象を取得
    targets = resolve_targets(card, act, item)
    events = []
    for tgt in targets:
        from_zone = tgt.get("zone")
        tgt["zone"] = to_zone
        events.append({
            "type": act["type"],
            "payload": {"cardId": tgt["id"], "fromZone": from_zone, "toZone": to_zone}
        })
    return events