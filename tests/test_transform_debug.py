# tests/test_transform_debug.py

import pytest
from decimal import Decimal
from actions.transform import handle_transform
from actions.select_option import handle_select_option
from lambda_function import apply_action
from helper import d

def test_transform_with_selection_key():
    """
    SelectOption → Transform のフロー全体をテスト
    """
    # テストカード
    card = {
        "id": "test-card-1",
        "baseCardId": "test_01", 
        "ownerId": "p1",
        "zone": "Field",
        "power": d(2000),
        "damage": d(1),
        "level": d(5),
        "effectList": []
    }
    
    # テストマッチ
    item = {
        "cards": [card.copy()],
        "choiceResponses": []
    }
    
    # SelectOption アクション（ランダム選択）
    select_action = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002", "token_003"],
        "weights": [d(10), d(40), d(50)],
        "selectionKey": "RandomSelectKey",
        "target": "PlayerField"
    }
    
    # SelectOption 実行
    select_events = apply_action(card, select_action, item, "p1")
    print(f"SelectOption events: {select_events}")
    
    # choiceResponses に選択結果が追加されていることを確認
    assert len(item["choiceResponses"]) == 1
    choice_resp = item["choiceResponses"][0]
    assert choice_resp["requestId"] == "RandomSelectKey"
    assert choice_resp["selectedValue"] in ["token_001", "token_002", "token_003"]
    
    selected_token = choice_resp["selectedValue"]
    print(f"Selected token: {selected_token}")
    
    # Transform アクション
    transform_action = {
        "type": "Transform",
        "target": "Self",
        "selectionKey": "RandomSelectKey"
    }
    
    # Transform 実行
    transform_events = apply_action(card, transform_action, item, "p1")
    print(f"Transform events: {transform_events}")
    
    # イベントが生成されていることを確認
    assert len(transform_events) >= 2  # MoveZone + CreateToken
    
    # MoveZone イベント確認
    move_event = next((e for e in transform_events if e["type"] == "MoveZone"), None)
    assert move_event is not None
    assert move_event["payload"]["cardId"] == "test-card-1"
    assert move_event["payload"]["fromZone"] == "Field"
    assert move_event["payload"]["toZone"] == "ExileZone"
    
    # CreateToken イベント確認
    token_event = next((e for e in transform_events if e["type"] == "CreateToken"), None)
    assert token_event is not None
    assert token_event["payload"]["baseCardId"] == selected_token
    assert token_event["payload"]["ownerId"] == "p1"
    assert token_event["payload"]["zone"] == "Field"  # 元のゾーンに生成
    
    # 元カードが ExileZone に移動していることを確認
    original_card = item["cards"][0]
    assert original_card["zone"] == "ExileZone"
    
    # 新しいトークンが追加されていることを確認
    assert len(item["cards"]) == 2  # 元カード + 新トークン
    new_token = item["cards"][1]
    assert new_token["baseCardId"] == selected_token
    assert new_token["zone"] == "Field"
    assert new_token["ownerId"] == "p1"
    
    print("✅ Transform with SelectOption test passed!")

if __name__ == "__main__":
    test_transform_with_selection_key()