# tests/test_random_integration.py
import pytest
import json
from unittest.mock import patch, MagicMock
from lambda_function import handle_trigger, apply_action


def test_select_option_transform_integration():
    """SelectOption → Transform の統合テスト"""
    # テストデータの準備
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "baseCardId": "original_card",
        "effectList": [
            {
                "trigger": "OnPlay",
                "actions": [
                    {
                        "type": "SelectOption",
                        "mode": "random",
                        "options": ["token_001", "token_002", "token_003"],
                        "weights": ["10", "40", "30"],
                        "selectionKey": "RandomSelectKey"
                    },
                    {
                        "type": "Transform",
                        "target": "Self",
                        "selectionKey": "RandomSelectKey"
                    }
                ]
            }
        ]
    }
    
    item = {
        "cards": [card],
        "choiceResponses": []
    }
    
    # randomをモック
    with patch('random.choices', return_value=["token_002"]):
        events = handle_trigger(card, "OnPlay", item)
    
    # 結果の検証
    assert len(events) >= 2  # AbilityActivated, SelectOption, Transform
    
    # SelectOptionイベントが正しく生成されているか確認
    select_event = next((e for e in events if e["type"] == "SelectOption"), None)
    assert select_event is not None
    assert select_event["payload"]["selectedValue"] == "token_002"
    
    # Transformイベントが正しく生成されているか確認
    transform_event = next((e for e in events if e["type"] == "Transform"), None)
    assert transform_event is not None
    assert transform_event["payload"]["toCardId"] == "token_002"
    
    # choiceResponsesに自動追加されているか確認
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["selectedValue"] == "token_002"
    
    # カードのbaseCardIdが変更されているか確認
    assert card["baseCardId"] == "token_002"


def test_select_option_create_token_integration():
    """SelectOption → CreateToken の統合テスト"""
    # テストデータの準備
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "effectList": [
            {
                "trigger": "OnPlay",
                "actions": [
                    {
                        "type": "SelectOption",
                        "mode": "random",
                        "options": ["token_001", "token_002", "token_003"],
                        "weights": ["10", "40", "30"],
                        "selectionKey": "RandomSelectKey"
                    },
                    {
                        "type": "CreateToken",
                        "tokenBaseIds": ["token_001", "token_002", "token_003"],
                        "target": "Field",
                        "value": "1"
                    }
                ]
            }
        ]
    }
    
    item = {
        "cards": [card],
        "choiceResponses": []
    }
    
    # randomをモック
    with patch('random.choices', return_value=["token_002"]):
        with patch('random.choice', return_value="token_002"):
            events = handle_trigger(card, "OnPlay", item)
    
    # 結果の検証
    assert len(events) >= 2  # AbilityActivated, SelectOption, CreateToken
    
    # SelectOptionイベントが正しく生成されているか確認
    select_event = next((e for e in events if e["type"] == "SelectOption"), None)
    assert select_event is not None
    assert select_event["payload"]["selectedValue"] == "token_002"
    
    # CreateTokenイベントが正しく生成されているか確認
    create_event = next((e for e in events if e["type"] == "CreateToken"), None)
    assert create_event is not None
    assert create_event["payload"]["baseCardId"] == "token_002"


def test_complex_random_flow():
    """複雑なランダムフロー（SelectOption → Transform → CreateToken）のテスト"""
    # 「可能性の繭」のようなカード
    card = {
        "id": "test_45",
        "ownerId": "player1",
        "baseCardId": "cocoon_card",
        "effectList": [
            {
                "trigger": "OnPlay",
                "actions": [
                    {
                        "type": "SelectOption",
                        "mode": "random",
                        "options": ["token_001", "token_002", "token_003", "token_004", "token_005"],
                        "weights": ["10", "40", "30", "15", "5"],
                        "selectionKey": "RandomSelectKey"
                    },
                    {
                        "type": "Transform",
                        "target": "Self",
                        "selectionKey": "RandomSelectKey"
                    }
                ]
            }
        ]
    }
    
    item = {
        "cards": [card],
        "choiceResponses": []
    }
    
    # randomをモック（重みに従って token_002 が選ばれる）
    with patch('random.choices', return_value=["token_002"]):
        events = handle_trigger(card, "OnPlay", item)
    
    # 結果の検証
    assert len(events) >= 3  # AbilityActivated, SelectOption, Transform
    
    # イベントの順序を確認
    event_types = [e["type"] for e in events]
    assert "AbilityActivated" in event_types
    assert "SelectOption" in event_types
    assert "Transform" in event_types
    
    # 選択結果の確認
    select_event = next((e for e in events if e["type"] == "SelectOption"), None)
    assert select_event["payload"]["selectedValue"] == "token_002"
    
    # 変身結果の確認
    transform_event = next((e for e in events if e["type"] == "Transform"), None)
    assert transform_event["payload"]["fromCardId"] == "cocoon_card"
    assert transform_event["payload"]["toCardId"] == "token_002"
    
    # 最終的なカードの状態確認
    assert card["baseCardId"] == "token_002"
    
    # choiceResponsesが正しく設定されているか確認
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["requestId"] == "RandomSelectKey"
    assert item["choiceResponses"][0]["selectedValue"] == "token_002"


def test_random_selection_edge_cases():
    """ランダム選択のエッジケースのテスト"""
    
    # 空の選択肢
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": [],
        "selectionKey": "EmptySelectKey"
    }
    item = {"choiceResponses": []}
    
    from actions.select_option import handle_select_option
    events = handle_select_option(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["payload"]["selectedOption"] is None
    
    # 重みの数が合わない場合
    act2 = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002"],
        "weights": ["10"],  # 重みが不足
        "selectionKey": "MismatchSelectKey"
    }
    item2 = {"choiceResponses": []}
    
    with patch('random.choice', return_value="token_001"):
        events2 = handle_select_option(card, act2, item2, "player1")
    
    assert len(events2) == 1
    assert events2[0]["payload"]["selectedValue"] == "token_001"


def test_apply_action_dispatch():
    """apply_action関数のディスパッチテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    # SelectOptionアクション
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002"],
        "selectionKey": "TestKey"
    }
    item = {"choiceResponses": []}
    
    with patch('random.choice', return_value="token_001"):
        events = apply_action(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert events[0]["payload"]["selectedValue"] == "token_001"