# actions/create_token.py
import uuid
from helper import weighted_random_select, fetch_card_masters, d

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
    
    # 選択される可能性のあるトークンIDを収集
    possible_token_ids = []
    if token_base_ids:
        possible_token_ids = token_base_ids
    else:
        possible_token_ids = [token_card_id]
    
    # カードマスターデータを事前に取得
    card_masters = fetch_card_masters(possible_token_ids)
    
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
            "level": d(1),
            "currentLevel": d(1),
            "power": d(1000),  # デフォルト値
            "currentPower": d(1000),
            "damage": d(0),
            "currentDamage": d(0),
            "statuses": [
                {"key": "IsToken", "value": True}
            ],
            "tempStatuses": [],
            "effectList": []
        }
        
        # カードマスターデータがある場合、基本属性を更新
        if selected_token_id in card_masters:
            master_data = card_masters[selected_token_id]
            
            # 基本属性の更新
            if "power" in master_data:
                token_card["power"] = d(master_data["power"])
                token_card["currentPower"] = d(master_data["power"])
            
            if "damage" in master_data:
                token_card["damage"] = d(master_data["damage"])
                token_card["currentDamage"] = d(master_data["damage"])
            
            if "level" in master_data:
                token_card["level"] = d(master_data["level"])
                token_card["currentLevel"] = d(master_data["level"])
            
            # effectList を更新（新しいカードの能力を取得）
            if "effectList" in master_data:
                token_card["effectList"] = master_data["effectList"]
        
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