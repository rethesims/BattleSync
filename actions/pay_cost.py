# actions/pay_cost.py

def handle_pay_cost(card, act, item, owner_id):
    """
    レベルポイントなどのコストを消費する
    """
    cost_type = act.get("keyword", "LevelPoint")  # LevelPoint, Energy, etc.
    cost_value = int(act.get("value", 0))
    
    # プレイヤー情報を取得
    player = next((p for p in item["players"] if p["id"] == owner_id), None)
    if not player:
        return []
    
    # コスト支払い処理
    if cost_type == "LevelPoint":
        # レベルポイントの消費
        current_level = player.get("levelPoints", 0)
        if current_level >= cost_value:
            player["levelPoints"] = current_level - cost_value
            return [{
                "type": "PayCost",
                "payload": {
                    "playerId": owner_id,
                    "costType": cost_type,
                    "costValue": cost_value,
                    "remainingValue": player["levelPoints"]
                }
            }]
        else:
            # コスト不足
            return [{
                "type": "PayCost",
                "payload": {
                    "playerId": owner_id,
                    "costType": cost_type,
                    "costValue": cost_value,
                    "error": "コストが不足しています"
                }
            }]
    
    # その他のコストタイプの場合
    return [{
        "type": "PayCost",
        "payload": {
            "playerId": owner_id,
            "costType": cost_type,
            "costValue": cost_value
        }
    }]