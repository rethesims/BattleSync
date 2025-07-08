# actions/set_player_status.py

def handle_set_player_status(card, act, item, owner_id):
    """
    ターン制限付きでプレイヤー状態を変更
    """
    target_player = act.get("target", "PlayerLeader")
    status_key = act.get("keyword", "Status")
    status_value = act.get("value", 1)
    duration = int(act.get("duration", 1))
    
    # 対象プレイヤーを決定
    if target_player == "PlayerLeader":
        target_player_id = owner_id
    elif target_player == "EnemyLeader":
        target_player_id = next((p["id"] for p in item["players"] if p["id"] != owner_id), None)
    else:
        target_player_id = owner_id
    
    if not target_player_id:
        return []
    
    # プレイヤー情報を取得
    player = next((p for p in item["players"] if p["id"] == target_player_id), None)
    if not player:
        return []
    
    # 期限を計算
    current_turn = item.get("turnCount", 0)
    expire_turn = current_turn + duration
    
    # プレイヤーの一時ステータスを設定
    temp_statuses = player.setdefault("tempStatuses", [])
    temp_statuses.append({
        "key": status_key,
        "value": status_value,
        "expireTurn": expire_turn
    })
    
    return [{
        "type": "SetPlayerStatus",
        "payload": {
            "playerId": target_player_id,
            "statusKey": status_key,
            "statusValue": status_value,
            "duration": duration,
            "expireTurn": expire_turn
        }
    }]