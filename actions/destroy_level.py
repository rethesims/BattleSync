# actions/destroy_level.py

def handle_destroy_level(card, act, item, owner_id):
    """
    レベルポイントを破壊（消費）
    """
    target_player = act.get("target", "PlayerLeader")
    destroy_value = int(act.get("value", 1))
    
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
    
    # レベルポイントを破壊
    current_level = player.get("levelPoints", 0)
    destroyed = min(current_level, destroy_value)
    player["levelPoints"] = current_level - destroyed
    
    return [{
        "type": "DestroyLevel",
        "payload": {
            "playerId": target_player_id,
            "destroyedValue": destroyed,
            "remainingValue": player["levelPoints"]
        }
    }]