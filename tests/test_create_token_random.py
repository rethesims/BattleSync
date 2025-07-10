# tests/test_create_token_random.py
import pytest
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.create_token import handle_create_token

def test_create_token_with_weighted_selection():
    """重み付きランダム選択を使用したトークン生成のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    act = {
        "type": "CreateToken",
        "target": "Field",
        "value": 2,  # 2個生成
        "tokenBaseIds": ["token_A", "token_B", "token_C"],
        "weights": [10, 30, 60]
    }
    
    item = {"cards": []}
    owner_id = "player1"
    
    # Mock weighted_random_select to return predictable results
    with patch('actions.create_token.weighted_random_select') as mock_select:
        mock_select.side_effect = ["token_B", "token_C"]
        
        events = handle_create_token(card, act, item, owner_id)
        
        # 2個のトークンが生成されることを確認
        assert len(events) == 2
        assert all(event["type"] == "CreateToken" for event in events)
        
        # 選択されたトークンIDが正しいことを確認
        assert events[0]["payload"]["baseCardId"] == "token_B"
        assert events[1]["payload"]["baseCardId"] == "token_C"
        
        # アイテムにトークンが追加されることを確認
        assert len(item["cards"]) == 2
        assert item["cards"][0]["baseCardId"] == "token_B"
        assert item["cards"][1]["baseCardId"] == "token_C"
        
        # weighted_random_select が正しく呼び出されることを確認
        assert mock_select.call_count == 2
        mock_select.assert_any_call(["token_A", "token_B", "token_C"], [10, 30, 60])

def test_create_token_without_weights():
    """重み指定なしの複数候補からのトークン生成のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    act = {
        "type": "CreateToken",
        "target": "Field",
        "value": 1,
        "tokenBaseIds": ["token_X", "token_Y"]
    }
    
    item = {"cards": []}
    owner_id = "player1"
    
    with patch('actions.create_token.weighted_random_select') as mock_select:
        mock_select.return_value = "token_X"
        
        events = handle_create_token(card, act, item, owner_id)
        
        assert len(events) == 1
        assert events[0]["payload"]["baseCardId"] == "token_X"
        
        # 均等重み（[1, 1]）で呼び出されることを確認
        mock_select.assert_called_with(["token_X", "token_Y"], [1, 1])

def test_create_token_traditional_single():
    """従来の単一トークン生成のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    act = {
        "type": "CreateToken",
        "target": "Field",
        "value": 1,
        "keyword": "traditional_token"
    }
    
    item = {"cards": []}
    owner_id = "player1"
    
    events = handle_create_token(card, act, item, owner_id)
    
    assert len(events) == 1
    assert events[0]["payload"]["baseCardId"] == "traditional_token"
    assert len(item["cards"]) == 1
    assert item["cards"][0]["baseCardId"] == "traditional_token"

def test_create_token_different_zones():
    """異なるゾーンへのトークン生成のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    test_zones = [
        ("Field", "Field"),
        ("Hand", "Hand"),
        ("Graveyard", "Graveyard"),
        ("Environment", "Environment"),
        ("Counter", "Counter"),
        ("ExileZone", "Exile"),
        ("DamageZone", "DamageZone"),
        ("UnknownZone", "Field")  # 不明なゾーンはFieldにマップ
    ]
    
    for target_zone, expected_zone in test_zones:
        act = {
            "type": "CreateToken",
            "target": target_zone,
            "value": 1,
            "keyword": "test_token"
        }
        
        item = {"cards": []}
        
        events = handle_create_token(card, act, item, "player1")
        
        assert len(events) == 1
        assert events[0]["payload"]["zone"] == expected_zone
        assert item["cards"][0]["zone"] == expected_zone

def test_create_token_properties():
    """生成されるトークンのプロパティテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    act = {
        "type": "CreateToken",
        "target": "Field",
        "value": 1,
        "keyword": "test_token"
    }
    
    item = {"cards": []}
    owner_id = "player1"
    
    events = handle_create_token(card, act, item, owner_id)
    
    created_token = item["cards"][0]
    
    # 基本プロパティの確認
    assert created_token["baseCardId"] == "test_token"
    assert created_token["ownerId"] == "player1"
    assert created_token["zone"] == "Field"
    assert created_token["isFaceUp"] is True
    assert created_token["level"] == 1
    assert created_token["power"] == 1000
    assert created_token["damage"] == 0
    
    # ステータスの確認
    assert len(created_token["statuses"]) == 1
    assert created_token["statuses"][0]["key"] == "IsToken"
    assert created_token["statuses"][0]["value"] is True
    
    # 空のリストの確認
    assert created_token["tempStatuses"] == []
    assert created_token["additionalEffects"] == []
    
    # IDが生成されていることを確認
    assert "id" in created_token
    assert created_token["id"] != ""

def test_create_token_multiple_count():
    """複数個のトークン生成のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    
    act = {
        "type": "CreateToken",
        "target": "Field",
        "value": 3,
        "keyword": "multi_token"
    }
    
    item = {"cards": []}
    owner_id = "player1"
    
    events = handle_create_token(card, act, item, owner_id)
    
    # 3個のトークンが生成されることを確認
    assert len(events) == 3
    assert len(item["cards"]) == 3
    
    # 各トークンが異なるIDを持つことを確認
    token_ids = [token["id"] for token in item["cards"]]
    assert len(set(token_ids)) == 3  # 全てユニークなID
    
    # 全て同じbaseCardIdを持つことを確認
    assert all(token["baseCardId"] == "multi_token" for token in item["cards"])