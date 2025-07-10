# actions/transform.py
import uuid
from helper import resolve_targets, fetch_card_masters, d, cleanup_used_choice_response

def handle_transform(card, act, item, owner_id):
    """
    Transform: 新しいトークンを生成し、元カードを ExileZone に移動
    SelectOption の結果に基づいて変身先トークンを決定
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"handle_transform: START - card={card.get('id')}, baseCardId={card.get('baseCardId')}, zone={card.get('zone')}")
    
    # 1. 変身先トークンIDを決定（SelectOption結果から）
    transform_to = _get_transform_target(act, item)
    logger.info(f"handle_transform: transform_to={transform_to}")
    
    if not transform_to:
        logger.info("handle_transform: transform_to is empty, returning empty events")
        return []
    
    # 元カードのゾーンを保存（ExileZone移動前に）
    original_zone = card["zone"]
    logger.info(f"handle_transform: original_zone={original_zone}")
    
    # 2. 元カード（Self）を ExileZone に移動
    logger.info("handle_transform: calling _move_card_to_exile")
    exile_events = _move_card_to_exile(card, item)
    logger.info(f"handle_transform: exile_events={exile_events}")
    
    # 3. 新しいトークンを生成（元カードの元々のゾーンに）
    logger.info("handle_transform: calling _create_transform_token")
    token_events = _create_transform_token(transform_to, card, item, owner_id, original_zone)
    logger.info(f"handle_transform: token_events={token_events}")
    
    logger.info(f"handle_transform: END - returning {len(exile_events + token_events)} events")
    return exile_events + token_events


def _get_transform_target(act, item):
    """変身先トークンIDを決定"""
    import logging
    logger = logging.getLogger(__name__)
    
    transform_to = ""
    
    # 1. selectionKey が指定されている場合、choiceResponses から取得
    selection_key = act.get("selectionKey")
    logger.info(f"_get_transform_target: selection_key={selection_key}")
    
    if selection_key:
        responses = item.get("choiceResponses", [])
        logger.info(f"_get_transform_target: choiceResponses={responses}")
        resp = next((r for r in responses if r.get("requestId") == selection_key), None)
        logger.info(f"_get_transform_target: found response={resp}")
        if resp:
            transform_to = resp.get("selectedValue", "")
            logger.info(f"_get_transform_target: selectedValue={transform_to}")
            # 使用済みchoiceResponseを削除
            cleanup_used_choice_response(item, selection_key)
    
    # 2. keyword パラメータ（従来通り）
    if not transform_to:
        transform_to = act.get("keyword", "")
        logger.info(f"_get_transform_target: keyword={transform_to}")
    
    # 3. transformTo パラメータ（直接指定）
    if not transform_to:
        transform_to = act.get("transformTo", "")
        logger.info(f"_get_transform_target: transformTo={transform_to}")
    
    # 4. options から選択（transformOptions配列）
    if not transform_to:
        options = act.get("options", [])
        if options:
            transform_to = options[0]  # 最初の選択肢をデフォルト
            logger.info(f"_get_transform_target: options[0]={transform_to}")
    
    logger.info(f"_get_transform_target: RESULT={transform_to}")
    return transform_to


def _move_card_to_exile(card, item):
    """元カードを ExileZone に移動"""
    import logging
    logger = logging.getLogger(__name__)
    
    from_zone = card.get("zone")
    logger.info(f"_move_card_to_exile: card={card.get('id')}, from_zone={from_zone}")
    
    card["zone"] = "ExileZone"
    logger.info(f"_move_card_to_exile: moved card to ExileZone")
    
    event = {
        "type": "MoveZone",
        "payload": {
            "cardId": card["id"],
            "fromZone": from_zone,
            "toZone": "ExileZone"
        }
    }
    logger.info(f"_move_card_to_exile: returning event={event}")
    return [event]


def _create_transform_token(transform_to, original_card, item, owner_id, original_zone):
    """新しいトークンを生成"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"_create_transform_token: transform_to={transform_to}, original_zone={original_zone}")
    
    # カードマスターデータを取得
    card_masters = fetch_card_masters([transform_to])
    logger.info(f"_create_transform_token: card_masters={card_masters}")
    
    # 新しいトークンを生成
    token_id = str(uuid.uuid4())
    token_card = {
        "id": token_id,
        "baseCardId": transform_to,
        "ownerId": owner_id,
        "zone": original_zone,  # 元カードの元々のゾーンに生成
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
    
    logger.info(f"_create_transform_token: created token_card with id={token_id}, zone={original_zone}")
    
    # カードマスターデータがある場合、基本属性を更新
    if transform_to in card_masters:
        master_data = card_masters[transform_to]
        logger.info(f"_create_transform_token: updating with master_data={master_data}")
        
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
    logger.info(f"_create_transform_token: added token to item[cards], total cards={len(item['cards'])}")
    
    # トークン生成イベントを生成
    event = {
        "type": "CreateToken",
        "payload": {
            "tokenId": token_id,
            "baseCardId": transform_to,
            "ownerId": owner_id,
            "zone": original_zone
        }
    }
    logger.info(f"_create_transform_token: returning event={event}")
    return [event]