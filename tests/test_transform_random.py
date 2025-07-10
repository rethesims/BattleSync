# tests/test_transform_random.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.transform import handle_transform

def test_transform_with_selection_key():
    """selectionKey を使用した変身のテスト - 新しいトークン生成 + 元カード Exile 移動"""
    # テスト用のカード
    original_card = {
        "id": "original_card",
        "baseCardId": "cocoon_card",
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
        "selectionKey": "random_transform"
    }
    
    # テスト用のアイテム
    item = {
        "cards": [original_card],
        "choiceResponses": [
            {
                "requestId": "random_transform",
                "selectedValue": "new_token_id"
            }
        ]
    }
    
    # Mock fetch_card_masters to return master data
    with patch('actions.transform.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "new_token_id": {
                "power": 3000,
                "damage": 1000,
                "level": 2,
                "effectList": [{"type": "SampleEffect"}]
            }
        }
        
        events = handle_transform(original_card, act, item, "player1")
        
        # 2つのイベントが生成されることを確認（MoveZone + CreateToken）
        assert len(events) == 2
        
        # 元カードが Exile に移動するイベント
        assert events[0]["type"] == "MoveZone"
        assert events[0]["payload"]["cardId"] == "original_card"
        assert events[0]["payload"]["fromZone"] == "Field"
        assert events[0]["payload"]["toZone"] == "Exile"
        
        # 新しいトークンが生成されるイベント
        assert events[1]["type"] == "CreateToken"
        assert events[1]["payload"]["baseCardId"] == "new_token_id"
        assert events[1]["payload"]["ownerId"] == "player1"
        assert events[1]["payload"]["zone"] == "Field"  # 元カードと同じゾーン
        
        # 元カードが Exile に移動していることを確認
        assert original_card["zone"] == "Exile"
        
        # 新しいトークンが item.cards に追加されていることを確認
        assert len(item["cards"]) == 2
        new_token = item["cards"][1]
        assert new_token["baseCardId"] == "new_token_id"
        assert new_token["ownerId"] == "player1"
        assert new_token["zone"] == "Field"
        assert new_token["power"] == 3000
        assert new_token["damage"] == 1000
        assert new_token["level"] == 2
        assert {"key": "IsToken", "value": True} in new_token["statuses"]
        
        # choiceResponse が削除されていることを確認
        assert len(item["choiceResponses"]) == 0

def test_transform_with_keyword():
    """keyword パラメータを使用した変身のテスト"""
    original_card = {
        "id": "original_card",
        "baseCardId": "base_card",
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
    
    item = {"cards": [original_card]}
    
    with patch('actions.transform.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "evolved_card": {
                "power": 2500,
                "damage": 800,
                "level": 3
            }
        }
        
        events = handle_transform(original_card, act, item, "player1")
        
        # 2つのイベントが生成されることを確認
        assert len(events) == 2
        assert events[0]["type"] == "MoveZone"
        assert events[1]["type"] == "CreateToken"
        assert events[1]["payload"]["baseCardId"] == "evolved_card"

def test_transform_with_options():
    """options パラメータを使用した変身のテスト"""
    original_card = {
        "id": "original_card",
        "baseCardId": "base_card",
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
    
    item = {"cards": [original_card]}
    
    with patch('actions.transform.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {"option1": {"power": 1500}}
        
        events = handle_transform(original_card, act, item, "player1")
        
        assert len(events) == 2
        assert events[1]["payload"]["baseCardId"] == "option1"  # 最初の選択肢

def test_transform_priority_order():
    """変身先決定の優先順位テスト"""
    original_card = {
        "id": "original_card",
        "baseCardId": "base_card",
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
        "cards": [original_card],
        "choiceResponses": [
            {
                "requestId": "selection_key",
                "selectedValue": "selected_card"
            }
        ]
    }
    
    with patch('actions.transform.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {"selected_card": {"power": 2000}}
        
        events = handle_transform(original_card, act, item, "player1")
        
        # selectionKey が最優先で使用される
        assert events[1]["payload"]["baseCardId"] == "selected_card"

def test_transform_no_target():
    """変身先が指定されていない場合のテスト"""
    original_card = {
        "id": "original_card",
        "baseCardId": "base_card",
        "ownerId": "player1",
        "zone": "Field",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self"
    }
    
    item = {"cards": [original_card]}
    
    events = handle_transform(original_card, act, item, "player1")
    
    # 変身先が指定されていない場合は何もしない
    assert len(events) == 0

def test_transform_cocoon_scenario():
    """可能性の繭カードのシナリオテスト - SelectOption → Transform の流れ"""
    cocoon_card = {
        "id": "cocoon_card_id",
        "baseCardId": "possibility_cocoon",
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
        "cards": [cocoon_card],
        "choiceResponses": [
            {
                "requestId": "RandomSelectKey",
                "selectedValue": "token_004"
            }
        ]
    }
    
    with patch('actions.transform.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "token_004": {
                "power": 4000,
                "damage": 1500,
                "level": 4,
                "effectList": [{"type": "PowerfulEffect"}]
            }
        }
        
        events = handle_transform(cocoon_card, act, item, "player1")
        
        # 2つのイベントが生成されることを確認
        assert len(events) == 2
        
        # 元の繭カードが Exile に移動
        assert events[0]["type"] == "MoveZone"
        assert events[0]["payload"]["cardId"] == "cocoon_card_id"
        assert events[0]["payload"]["toZone"] == "Exile"
        
        # 新しいトークンが生成される
        assert events[1]["type"] == "CreateToken"
        assert events[1]["payload"]["baseCardId"] == "token_004"
        assert events[1]["payload"]["zone"] == "Field"
        
        # 元カードが Exile に移動していることを確認
        assert cocoon_card["zone"] == "Exile"
        
        # 新しいトークンが追加されていることを確認
        assert len(item["cards"]) == 2
        new_token = item["cards"][1]
        assert new_token["baseCardId"] == "token_004"
        assert new_token["power"] == 4000
        assert new_token["damage"] == 1500
        assert new_token["level"] == 4
        assert {"key": "IsToken", "value": True} in new_token["statuses"]

# patch のインポート
from unittest.mock import patch