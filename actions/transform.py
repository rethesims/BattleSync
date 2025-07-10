# actions/transform.py
import uuid
from helper import resolve_targets, fetch_card_masters, d, cleanup_used_choice_response

def handle_transform(card, act, item, owner_id):
    """
    Transform: 新しいトークンを生成し、元カードを ExileZone に移動
    SelectOption の結果に基づいて変身先トークンを決定
    """
    # 1. 変身先トークンIDを決定（SelectOption結果から）
    transform_to = _get_transform_target(act, item)
    
    if not transform_to:
        return []
    
    # 2. 元カード（Self）を ExileZone に移動
    exile_events = _move_card_to_exile(card, item)
    
    # 3. 新しいトークンを生成（元カードと同じゾーンに）
    token_events = _create_transform_token(transform_to, card, item, owner_id)
    
    return exile_events + token_events


def _get_transform_target(act, item):
    """変身先トークンIDを決定"""
    transform_to = ""
    
    # 1. selectionKey が指定されている場合、choiceResponses から取得
    selection_key = act.get("selectionKey")
    if selection_key:
        responses = item.get("choiceResponses", [])
        resp = next((r for r in responses if r.get("requestId") == selection_key), None)
        if resp:
            transform_to = resp.get("selectedValue", "")
            # 使用済みchoiceResponseを削除
            cleanup_used_choice_response(item, selection_key)
    
    # 2. keyword パラメータ（従来通り）
    if not transform_to:
        transform_to = act.get("keyword", "")
    
    # 3. transformTo パラメータ（直接指定）
    if not transform_to:
        transform_to = act.get("transformTo", "")
    
    # 4. options から選択（transformOptions配列）
    if not transform_to:
        options = act.get("options", [])
        if options:
            transform_to = options[0]  # 最初の選択肢をデフォルト
    
    return transform_to


def _move_card_to_exile(card, item):
    """元カードを ExileZone に移動"""
    from_zone = card.get("zone")
    card["zone"] = "ExileZone"
    
    return [{
        "type": "MoveZone",
        "payload": {
            "cardId": card["id"],
            "fromZone": from_zone,
            "toZone": "ExileZone"
        }
    }]


def _create_transform_token(transform_to, original_card, item, owner_id):
    """新しいトークンを生成"""
    # カードマスターデータを取得
    card_masters = fetch_card_masters([transform_to])
    
    # 新しいトークンを生成
    token_id = str(uuid.uuid4())
    token_card = {
        "id": token_id,
        "baseCardId": transform_to,
        "ownerId": owner_id,
        "zone": original_card["zone"],  # 元カードと同じゾーンに生成
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
    if transform_to in card_masters:
        master_data = card_masters[transform_to]
        
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
    return [{
        "type": "CreateToken",
        "payload": {
            "tokenId": token_id,
            "baseCardId": transform_to,
            "ownerId": owner_id,
            "zone": original_card["zone"]
        }
    }]