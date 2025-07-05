# actions/draw.py

def handle_draw(card, act, item, owner_id):
    """
    act["value"] 回だけドロー処理を行い、
    成功した枚数を payload.count に含めた Draw イベントを返す。
    target が "PlayerLeader"/"EnemyLeader" なら対象プレイヤーを切り替え。
    """
    print(f"Handling Draw action: {act} for card {card['id']} by player {owner_id}")
    # ① 引く回数を取得（デフォルト１）
    try:
        draw_times = int(act.get("value", 1))
    except (TypeError, ValueError):
        draw_times = 1

    # ② どのプレイヤーが引くか判定
    tgt = act.get("target", "")
    if tgt == "PlayerLeader":
        player_to_draw = owner_id
    elif tgt == "EnemyLeader":
        player_to_draw = next(p["id"] for p in item["players"] if p["id"] != owner_id)
    else:
        player_to_draw = owner_id

    # ③ ドロー処理
    drawn = 0
    for _ in range(draw_times):
        deck_card = next(
            (c for c in item["cards"]
             if c["ownerId"] == player_to_draw and c["zone"] == "Deck"),
            None
        )
        if not deck_card:
            break
        deck_card["zone"] = "Hand"
        drawn += 1

    # ④ Draw イベントをまとめて返す
    return [{
        "type": "Draw",
        "payload": {"playerId": player_to_draw, "count": drawn}
    }]