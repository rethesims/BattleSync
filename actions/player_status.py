# actions/player_status.py

def handle_player_status(card, act, item, owner_id):
    """
    プレイヤー単位のステータスを永続的に変更
    """
    target_player = act.get("target", "PlayerLeader")
    status_key = act.get("keyword", "Status")
    status_value = act.get("value", 1)
    
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
    
    # プレイヤーステータスを設定
    player_statuses = player.setdefault("statuses", [])
    
    # 既存のステータスを更新または新規追加
    existing_status = next((s for s in player_statuses if s["key"] == status_key), None)
    if existing_status:
        existing_status["value"] = status_value
    else:
        player_statuses.append({
            "key": status_key,
            "value": status_value
        })
    
    return [{
        "type": "PlayerStatus",
        "payload": {
            "playerId": target_player_id,
            "statusKey": status_key,
            "statusValue": status_value
        }
    }]