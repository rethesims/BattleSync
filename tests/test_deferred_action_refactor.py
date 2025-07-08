"""
遅延（deferred）アクション対応のリファクタのテスト

テストケース:
1. 即座実行アクション（deferred=false）のみ
2. 遅延実行アクション（deferred=true）のみ  
3. 混合アクション（即座+遅延）
4. OnChoiceCompleteイベント処理
5. deferredActionsのクリア
6. 使用済みchoiceResponsesのクリア
"""

import pytest
import json
from unittest.mock import Mock, patch
from lambda_function import handle_trigger, resolve, _cleanup_used_choice_response


def create_test_item():
    """テスト用のマッチ状態オブジェクトを作成"""
    return {
        "id": "test_match",
        "cards": [
            {
                "id": "card_1", 
                "ownerId": "player_1", 
                "zone": "Field",
                "effectList": []
            },
            {
                "id": "card_2", 
                "ownerId": "player_2", 
                "zone": "Field",
                "effectList": []
            }
        ],
        "players": [
            {"id": "player_1", "name": "Player1"},
            {"id": "player_2", "name": "Player2"}
        ],
        "deferredActions": [],
        "choiceResponses": []
    }


def test_immediate_actions_only():
    """即座実行アクション（deferred=false）のみのテスト"""
    item = create_test_item()
    
    card = {
        "id": "test_card",
        "ownerId": "player_1",
        "effectList": [
            {
                "trigger": "OnSummon",
                "actions": [
                    {"type": "Draw", "target": "Self", "deferred": False},
                    {"type": "PowerAura", "target": "Self", "value": 1000, "deferred": False}
                ]
            }
        ]
    }
    
    # handle_triggerを実行
    with patch('lambda_function.apply_action') as mock_apply:
        mock_apply.return_value = [{"type": "TestEvent", "payload": {}}]
        events = handle_trigger(card, "OnSummon", item)
    
    # 検証
    assert len(events) == 3  # AbilityActivated + 2つのアクション結果
    assert events[0]["type"] == "AbilityActivated"
    assert mock_apply.call_count == 2  # 2つのアクションが即座実行される
    assert len(item["deferredActions"]) == 0  # 遅延アクションなし
    
    # SendChoiceRequestイベントが生成されないことを確認
    choice_requests = [e for e in events if e["type"] == "SendChoiceRequest"]
    assert len(choice_requests) == 0


def test_deferred_actions_only():
    """遅延実行アクション（deferred=true）のみのテスト"""
    item = create_test_item()
    
    card = {
        "id": "test_card",
        "ownerId": "player_1",
        "effectList": [
            {
                "trigger": "OnSummon",
                "actions": [
                    {
                        "type": "Destroy", 
                        "target": "EnemyField", 
                        "selectionKey": "destroyTarget",
                        "deferred": True
                    },
                    {
                        "type": "Bounce", 
                        "target": "EnemyField", 
                        "selectionKey": "bounceTarget",
                        "deferred": True
                    }
                ]
            }
        ]
    }
    
    # handle_triggerを実行
    with patch('lambda_function.apply_action') as mock_apply:
        events = handle_trigger(card, "OnSummon", item)
    
    # 検証
    assert len(events) == 2  # AbilityActivated + SendChoiceRequest
    assert events[0]["type"] == "AbilityActivated"
    assert events[1]["type"] == "SendChoiceRequest"
    assert mock_apply.call_count == 0  # 即座実行アクションなし
    
    # deferredActionsに保存されているか確認
    assert len(item["deferredActions"]) == 2
    assert item["deferredActions"][0]["type"] == "Destroy"
    assert item["deferredActions"][0]["sourceCardId"] == "test_card"
    assert item["deferredActions"][0]["trigger"] == "OnSummon"
    assert item["deferredActions"][1]["type"] == "Bounce"
    
    # SendChoiceRequestの内容確認
    choice_request = events[1]
    assert choice_request["payload"]["requestId"] == "destroyTarget"
    assert choice_request["payload"]["playerId"] == "player_1"


def test_mixed_actions():
    """混合アクション（即座+遅延）のテスト"""
    item = create_test_item()
    
    card = {
        "id": "test_card",
        "ownerId": "player_1",
        "effectList": [
            {
                "trigger": "OnSummon",
                "actions": [
                    {
                        "type": "Select", 
                        "target": "EnemyField", 
                        "selectionKey": "targetCard",
                        "mode": "single",
                        "deferred": False
                    },
                    {
                        "type": "Destroy", 
                        "selectionKey": "targetCard",
                        "deferred": True
                    }
                ]
            }
        ]
    }
    
    # handle_triggerを実行
    with patch('lambda_function.apply_action') as mock_apply:
        mock_apply.return_value = [{"type": "SendChoiceRequest", "payload": {}}]
        events = handle_trigger(card, "OnSummon", item)
    
    # 検証
    assert len(events) == 3  # AbilityActivated + SendChoiceRequest + Selectアクション結果
    assert events[0]["type"] == "AbilityActivated"
    assert events[1]["type"] == "SendChoiceRequest"
    assert mock_apply.call_count == 1  # Selectアクションのみ即座実行
    
    # deferredActionsに保存されているか確認
    assert len(item["deferredActions"]) == 1
    assert item["deferredActions"][0]["type"] == "Destroy"
    assert item["deferredActions"][0]["selectionKey"] == "targetCard"


def test_onchoicecomplete_processing():
    """OnChoiceCompleteイベント処理のテスト"""
    item = create_test_item()
    
    # 事前にdeferredActionsを設定
    item["deferredActions"] = [
        {
            "type": "Destroy",
            "selectionKey": "targetCard",
            "sourceCardId": "card_1",
            "trigger": "OnSummon"
        }
    ]
    
    # choiceResponsesを設定
    item["choiceResponses"] = [
        {
            "requestId": "targetCard",
            "selectedIds": ["card_2"]
        }
    ]
    
    # OnChoiceCompleteイベントを作成
    initial_events = [
        {
            "type": "OnChoiceComplete",
            "payload": {}
        }
    ]
    
    # resolveを実行
    with patch('lambda_function.apply_action') as mock_apply:
        mock_apply.return_value = [{"type": "Destroyed", "payload": {"cardId": "card_2"}}]
        events = resolve(initial_events, item)
    
    # 検証
    assert mock_apply.call_count == 1  # deferredActionが実行される
    assert len(item["deferredActions"]) == 0  # 実行後クリアされる
    
    # choiceResponsesがクリアされることを確認
    remaining_responses = [r for r in item["choiceResponses"] if r["requestId"] == "targetCard"]
    assert len(remaining_responses) == 0


def test_cleanup_used_choice_response():
    """使用済みchoiceResponsesのクリア処理テスト"""
    item = {
        "choiceResponses": [
            {"requestId": "targetCard", "selectedIds": ["card_1"]},
            {"requestId": "otherRequest", "selectedIds": ["card_2"]},
            {"requestId": "targetCard", "selectedIds": ["card_3"]}  # 同じrequestIdが複数
        ]
    }
    
    # targetCardのレスポンスをクリア
    _cleanup_used_choice_response(item, "targetCard")
    
    # 検証
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["requestId"] == "otherRequest"


def test_default_selection_key_generation():
    """selectionKeyが指定されていない場合のデフォルト生成テスト"""
    item = create_test_item()
    
    card = {
        "id": "test_card",
        "ownerId": "player_1",
        "effectList": [
            {
                "trigger": "OnSummon",
                "actions": [
                    {
                        "type": "Destroy", 
                        "target": "EnemyField",
                        "deferred": True
                        # selectionKeyなし
                    }
                ]
            }
        ]
    }
    
    # handle_triggerを実行
    with patch('lambda_function.apply_action') as mock_apply:
        events = handle_trigger(card, "OnSummon", item)
    
    # デフォルトのselectionKeyが生成されることを確認
    assert len(item["deferredActions"]) == 1
    assert item["deferredActions"][0]["selectionKey"] == "deferred_test_card_OnSummon"
    
    # SendChoiceRequestにも同じキーが使用されることを確認
    choice_request = next(e for e in events if e["type"] == "SendChoiceRequest")
    assert choice_request["payload"]["requestId"] == "deferred_test_card_OnSummon"


def test_no_deferred_actions():
    """deferredActionsがない場合のテスト"""
    item = create_test_item()
    
    card = {
        "id": "test_card",
        "ownerId": "player_1",
        "effectList": [
            {
                "trigger": "OnSummon",
                "actions": [
                    {"type": "Draw", "target": "Self"}  # deferredフラグなし（デフォルトfalse）
                ]
            }
        ]
    }
    
    # handle_triggerを実行
    with patch('lambda_function.apply_action') as mock_apply:
        mock_apply.return_value = []
        events = handle_trigger(card, "OnSummon", item)
    
    # SendChoiceRequestイベントが生成されないことを確認
    choice_requests = [e for e in events if e["type"] == "SendChoiceRequest"]
    assert len(choice_requests) == 0
    assert len(item["deferredActions"]) == 0


if __name__ == "__main__":
    pytest.main([__file__])