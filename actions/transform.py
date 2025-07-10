# actions/transform.py
import uuid
import logging
from helper import resolve_targets, fetch_card_masters, d, cleanup_used_choice_response

logger = logging.getLogger()

def handle_transform(card, act, item, owner_id):
    """
    Transform: 新しいトークンを生成し、元カードを Exile に移動
    SelectOption の結果に基づいて変身先トークンを決定
    """
    logger.info(f"handle_transform: START - Transform処理開始 card={card['id']} owner={owner_id}")
    
    # --- ① スロット演出用のイベントを先出し ---
    selection_key = act.get("selectionKey")
    options = act.get("options", [])
    selected = ""
    
    # choiceResponses から選択済み値を拾う
    if selection_key:
        resp = next((r for r in item.get("choiceResponses", []) if r.get("requestId") == selection_key), None)
        if resp:
            selected = resp.get("selectedValue", "")
    
    slot_event = {
        "type": "SelectOptionResult",
        "payload": {
            "selectionKey": selection_key,
            "options": options,
            "selectedValue": selected
        }
    }
    logger.info(f"handle_transform: Slot event created selectionKey={selection_key}, selectedValue={selected}")
    
    # 元のゾーンを保存
    original_zone = card.get("zone")
    logger.info(f"handle_transform: original zone={original_zone}")
    
    # 1. 変身先トークンIDを決定（SelectOption結果から）
    transform_to = _get_transform_target(act, item)
    
    if not transform_to:
        logger.warning(f"handle_transform: No transform target found for card {card['id']}")
        return [slot_event]
    
    # 2. 元カード（Self）を Exile に移動
    exile_events = _move_card_to_exile(card, item)
    
    # 3. 新しいトークンを生成（元カードと同じゾーンに）
    token_events = _create_transform_token(transform_to, card, item, owner_id, original_zone)
    
    logger.info(f"handle_transform: COMPLETE - Transform処理完了 transform_to={transform_to}")
    return [slot_event] + exile_events + token_events


def _get_transform_target(act, item):
    """変身先トークンIDを決定"""
    logger.info(f"_get_transform_target: START - 変身先決定開始")
    transform_to = ""
    
    # 1. selectionKey が指定されている場合、choiceResponses から取得
    selection_key = act.get("selectionKey")
    if selection_key:
        logger.info(f"_get_transform_target: selectionKey={selection_key}")
        responses = item.get("choiceResponses", [])
        resp = next((r for r in responses if r.get("requestId") == selection_key), None)
        if resp:
            transform_to = resp.get("selectedValue", "")
            logger.info(f"_get_transform_target: Found selectedValue from choiceResponses: {transform_to}")
            # 使用済みchoiceResponseを削除
            cleanup_used_choice_response(item, selection_key)
        else:
            logger.warning(f"_get_transform_target: No matching choiceResponse found for selectionKey: {selection_key}")
    
    # 2. keyword パラメータ（従来通り）
    if not transform_to:
        transform_to = act.get("keyword", "")
        if transform_to:
            logger.info(f"_get_transform_target: Using keyword parameter: {transform_to}")
    
    # 3. transformTo パラメータ（直接指定）
    if not transform_to:
        transform_to = act.get("transformTo", "")
        if transform_to:
            logger.info(f"_get_transform_target: Using transformTo parameter: {transform_to}")
    
    # 4. options から選択（transformOptions配列）
    if not transform_to:
        options = act.get("options", [])
        if options:
            transform_to = options[0]  # 最初の選択肢をデフォルト
            logger.info(f"_get_transform_target: Using first option: {transform_to}")
    
    logger.info(f"_get_transform_target: RESULT={transform_to}")
    return transform_to


def _move_card_to_exile(card, item):
    """元カードを Exile に移動"""
    from_zone = card.get("zone")
    logger.info(f"_move_card_to_exile: Moving card {card['id']} from {from_zone} to Exile")
    card["zone"] = "Exile"
    logger.info(f"_move_card_to_exile: moved card to Exile")
    
    return [{
        "type": "MoveZone",
        "payload": {
            "cardId": card["id"],
            "fromZone": from_zone,
            "toZone": "Exile"
        }
    }]


def _create_transform_token(transform_to, original_card, item, owner_id, original_zone):
    """新しいトークンを生成"""
    logger.info(f"_create_transform_token: START - Creating token {transform_to} in zone {original_zone}")
    
    # カードマスターデータを取得
    card_masters = fetch_card_masters([transform_to])
    logger.info(f"_create_transform_token: Fetched card masters for {transform_to}")
    
    # 新しいトークンを生成
    token_id = str(uuid.uuid4())
    token_card = {
        "id": token_id,
        "baseCardId": transform_to,
        "ownerId": owner_id,
        "zone": original_zone,  # 元のゾーンに生成（保存済みの元のゾーンを使用）
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
    
    logger.info(f"_create_transform_token: Created token card with id={token_id} zone={original_zone}")
    
    # カードマスターデータがある場合、基本属性を更新
    if transform_to in card_masters:
        master_data = card_masters[transform_to]
        logger.info(f"_create_transform_token: Updating token attributes from master data")
        
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
    else:
        logger.warning(f"_create_transform_token: No master data found for {transform_to}")
    
    # マッチのカードリストに追加
    item["cards"].append(token_card)
    logger.info(f"_create_transform_token: added token to item[cards] - トークン追加（フィールドに追加）")
    
    # トークン生成イベントを生成
    return [{
        "type": "CreateToken",
        "payload": {
            "tokenId": token_id,
            "baseCardId": transform_to,
            "ownerId": owner_id,
            "zone": original_zone
        }
    }]