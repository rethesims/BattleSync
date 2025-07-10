# tests/test_transform_random.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.transform import handle_transform

def test_transform_with_selection_key():
    """selectionKey を使用した変身のテスト"""
    # テスト用のカード
    card = {"id": "test_card", "ownerId": "player1"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [{"key": "TestStatus", "value": "test"}],
        "tempStatuses": [],
        "power": 2000,
        "damage": 500
    }
    
    # テスト用のアクション
    act = {
        "type": "Transform",
        "target": "Self",
        "selectionKey": "random_transform",
        "resetStatuses": True,
        "resetPower": True,
        "resetDamage": True
    }
    
    # テスト用のアイテム
    item = {
        "cards": [card, target_card],
        "choiceResponses": [
            {
                "requestId": "random_transform",
                "selectedValue": "new_card_id"
            }
        ]
    }
    
    # Mock resolve_targets to return target_card
    with patch('actions.transform.resolve_targets') as mock_resolve:
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        # イベントが正しく生成されることを確認
        assert len(events) == 1
        assert events[0]["type"] == "Transform"
        assert events[0]["payload"]["cardId"] == "target_card"
        assert events[0]["payload"]["fromCardId"] == "original_card"
        assert events[0]["payload"]["toCardId"] == "new_card_id"
        assert events[0]["payload"]["resetStatuses"] is True
        assert events[0]["payload"]["resetPower"] is True
        assert events[0]["payload"]["resetDamage"] is True
        
        # カードが変身していることを確認
        assert target_card["baseCardId"] == "new_card_id"
        assert target_card["statuses"] == []  # リセットされている
        assert target_card["power"] == 1000   # デフォルト値
        assert target_card["damage"] == 0     # リセット

def test_transform_with_keyword():
    """keyword パラメータを使用した変身のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self",
        "keyword": "evolved_card"
    }
    
    item = {"cards": [card, target_card]}
    
    with patch('actions.transform.resolve_targets') as mock_resolve:
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        assert len(events) == 1
        assert events[0]["payload"]["toCardId"] == "evolved_card"
        assert target_card["baseCardId"] == "evolved_card"

def test_transform_with_options():
    """options パラメータを使用した変身のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self",
        "options": ["option1", "option2", "option3"]
    }
    
    item = {"cards": [card, target_card]}
    
    with patch('actions.transform.resolve_targets') as mock_resolve:
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        assert len(events) == 1
        assert events[0]["payload"]["toCardId"] == "option1"  # 最初の選択肢
        assert target_card["baseCardId"] == "option1"

def test_transform_priority_order():
    """変身先決定の優先順位テスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    # selectionKey が最優先
    act = {
        "type": "Transform",
        "target": "Self",
        "selectionKey": "selection_key",
        "keyword": "keyword_card",
        "transformTo": "transform_to_card",
        "options": ["option1", "option2"]
    }
    
    item = {
        "cards": [card, target_card],
        "choiceResponses": [
            {
                "requestId": "selection_key",
                "selectedValue": "selected_card"
            }
        ]
    }
    
    with patch('actions.transform.resolve_targets') as mock_resolve:
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        # selectionKey が最優先で使用される
        assert events[0]["payload"]["toCardId"] == "selected_card"

def test_transform_no_target():
    """変身先が指定されていない場合のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self"
    }
    
    item = {"cards": [card, target_card]}
    
    with patch('actions.transform.resolve_targets') as mock_resolve:
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        # 変身先が指定されていない場合は何もしない
        assert len(events) == 0

def test_transform_with_selection_key_and_target():
    """selectionKey と target が同時に指定されている場合のテスト"""
    card = {"id": "test_card", "ownerId": "player1", "zone": "Field"}
    target_card = {
        "id": "target_card",
        "baseCardId": "original_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self",
        "selectionKey": "RandomSelectKey"
    }
    
    item = {
        "cards": [card, target_card],
        "choiceResponses": [
            {
                "requestId": "RandomSelectKey",
                "selectedValue": "token_004"
            }
        ]
    }
    
    with patch('actions.transform.resolve_targets') as mock_resolve:
        # resolve_targets が正しく呼び出されることを確認
        mock_resolve.return_value = [target_card]
        
        events = handle_transform(card, act, item, "player1")
        
        # resolve_targets が selectionKey なしで呼び出されることを確認
        assert mock_resolve.called
        call_args = mock_resolve.call_args[0]
        action_passed = call_args[1]
        assert "selectionKey" not in action_passed
        assert action_passed["target"] == "Self"
        
        # 変身が正しく実行されることを確認
        assert len(events) == 1
        assert events[0]["type"] == "Transform"
        assert events[0]["payload"]["toCardId"] == "token_004"
        assert target_card["baseCardId"] == "token_004"

# patch のインポート
from unittest.mock import patch