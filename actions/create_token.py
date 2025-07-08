# actions/create_token.py
import uuid

def handle_create_token(card, act, item, owner_id):
    """
    指定のトークンカードを生成
    """
    token_card_id = act.get("keyword", "Token")  # トークンのベースカードID
    token_zone = act.get("target", "Field")  # 生成先ゾーン
    token_count = int(act.get("value", 1))  # 生成数
    events = []
    
    # マップ用のzone名を変換
    zone_map = {
        "Field": "Field",
        "Hand": "Hand",
        "Deck": "Deck",
        "Graveyard": "Graveyard"
    }
    
    target_zone = zone_map.get(token_zone, "Field")
    
    for _ in range(token_count):
        # 新しいトークンを生成
        token_id = str(uuid.uuid4())
        token_card = {
            "id": token_id,
            "baseCardId": token_card_id,
            "ownerId": owner_id,
            "zone": target_zone,
            "isFaceUp": True,
            "level": 1,
            "power": 1000,  # デフォルト値
            "damage": 0,
            "statuses": [
                {"key": "IsToken", "value": True}
            ],
            "tempStatuses": [],
            "additionalEffects": []
        }
        
        # マッチのカードリストに追加
        item["cards"].append(token_card)
        
        # トークン生成イベントを生成
        events.append({
            "type": "CreateToken",
            "payload": {
                "tokenId": token_id,
                "baseCardId": token_card_id,
                "ownerId": owner_id,
                "zone": target_zone
            }
        })
    
    return events