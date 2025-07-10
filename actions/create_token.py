# actions/create_token.py
import uuid
from helper import weighted_random_select

def handle_create_token(card, act, item, owner_id):
    """
    指定のトークンカードを生成
    複数候補からの重み付きランダム選択に対応
    """
    # 従来の単一トークン生成
    token_card_id = act.get("keyword", "Token")  # トークンのベースカードID
    token_zone = act.get("target", "Field")  # 生成先ゾーン
    token_count = int(act.get("value", 1))  # 生成数
    
    # 複数候補からのランダム選択
    token_base_ids = act.get("tokenBaseIds", [])  # 複数のトークンベースID
    weights = act.get("weights", [])  # 重み配列
    
    events = []
    
    # マップ用のzone名を変換
    zone_map = {
        "Field": "Field",
        "Hand": "Hand",
        "Deck": "Deck",
        "Graveyard": "Graveyard",
        "Environment": "Environment",
        "Counter": "Counter",
        "ExileZone": "ExileZone",
        "DamageZone": "DamageZone"
    }
    
    target_zone = zone_map.get(token_zone, "Field")
    
    for _ in range(token_count):
        # トークンベースIDを決定
        selected_token_id = ""
        
        # 複数候補からランダム選択
        if token_base_ids:
            if weights and len(weights) == len(token_base_ids):
                # 重み付きランダム選択
                weight_values = [int(w) for w in weights]
                selected_token_id = weighted_random_select(token_base_ids, weight_values)
            else:
                # 重みが指定されていない場合は均等選択
                selected_token_id = weighted_random_select(token_base_ids, [1] * len(token_base_ids))
        else:
            # 従来の単一トークン生成
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