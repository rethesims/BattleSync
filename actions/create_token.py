# actions/create_token.py
import uuid
import random

def handle_create_token(card, act, item, owner_id):
    """
    指定のトークンカードを生成（重み付きランダム選択対応）
    """
    events = []
    
    # トークンタイプを決定
    token_base_ids = act.get("tokenBaseIds", [])
    weights = act.get("weights", [])
    
    # tokenBaseIdsが指定されている場合は重み付きランダム選択
    if token_base_ids:
        if weights and len(weights) == len(token_base_ids):
            # 重み付きランダム選択
            numeric_weights = [float(w) for w in weights]
            token_card_id = random.choices(token_base_ids, weights=numeric_weights)[0]
        else:
            # 均等ランダム選択
            token_card_id = random.choice(token_base_ids)
    else:
        # 従来の単一トークンタイプ
        token_card_id = act.get("keyword", "Token")
    
    token_zone = act.get("target", "Field")  # 生成先ゾーン
    token_count = int(act.get("value", 1))  # 生成数
    
    # マップ用のzone名を変換
    zone_map = {
        "Field": "Field",
        "Hand": "Hand",
        "Deck": "Deck",
        "Graveyard": "Graveyard"
    }
    
    target_zone = zone_map.get(token_zone, "Field")
    
    for _ in range(token_count):
        # 各トークンで個別に重み付きランダム選択を実行（指定されている場合）
        if token_base_ids:
            if weights and len(weights) == len(token_base_ids):
                # 重み付きランダム選択
                numeric_weights = [float(w) for w in weights]
                selected_token_id = random.choices(token_base_ids, weights=numeric_weights)[0]
            else:
                # 均等ランダム選択
                selected_token_id = random.choice(token_base_ids)
        else:
            selected_token_id = token_card_id
        
        # 新しいトークンを生成
        token_id = str(uuid.uuid4())
        token_card = {
            "id": token_id,
            "baseCardId": selected_token_id,
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
                "baseCardId": selected_token_id,
                "ownerId": owner_id,
                "zone": target_zone
            }
        })
    
    return events