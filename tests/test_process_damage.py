# tests/test_process_damage.py
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.process_damage import handle_process_damage, check_reflection_damage, process_to_selection_result

def test_process_damage_basic():
    """基本的なダメージ処理のテスト"""
    # テストデータ
    card = {"id": "attacker1", "ownerId": "player1"}
    act = {"value": 2, "targetPlayerId": "player2"}
    item = {
        "players": [
            {"id": "player1", "hp": 20},
            {"id": "player2", "hp": 20}
        ],
        "cards": [
            {"id": "deck1", "cardId": "card1", "zone": "Deck", "ownerId": "player2"},
            {"id": "deck2", "cardId": "card2", "zone": "Deck", "ownerId": "player2"},
            {"id": "deck3", "cardId": "card3", "zone": "Deck", "ownerId": "player2"}
        ]
    }
    owner_id = "player1"
    
    # モックカードマスターデータ
    mock_card_masters = {
        "card1": {"name": "Test Card 1", "isTO": False, "availableColors": ["Red", "Blue"]},
        "card2": {"name": "Test Card 2", "isTO": False, "availableColors": ["Green", "Yellow"]}
    }
    
    with patch('actions.process_damage.fetch_card_masters', return_value=mock_card_masters):
        events = handle_process_damage(card, act, item, owner_id)
    
    # 結果検証
    assert len(events) >= 4  # MoveZone x2 + AssignColor x2 + AbilityActivated
    
    # MoveZoneイベントの検証
    move_events = [e for e in events if e["type"] == "MoveZone"]
    assert len(move_events) == 2
    assert move_events[0]["payload"]["fromZone"] == "Deck"
    assert move_events[0]["payload"]["toZone"] == "DamageZone"
    
    # AssignColorイベントの検証
    assign_color_events = [e for e in events if e["type"] == "AssignColor"]
    assert len(assign_color_events) == 2
    
    # OnDamageトリガーの検証
    ability_events = [e for e in events if e["type"] == "AbilityActivated"]
    assert len(ability_events) == 1
    assert ability_events[0]["payload"]["trigger"] == "OnDamage"

def test_process_damage_with_to_card():
    """TOカードを含むダメージ処理のテスト"""
    # テストデータ
    card = {"id": "attacker1", "ownerId": "player1"}
    act = {"value": 1, "targetPlayerId": "player2"}
    item = {
        "players": [
            {"id": "player1", "hp": 20},
            {"id": "player2", "hp": 20}
        ],
        "cards": [
            {"id": "deck1", "cardId": "to_card1", "zone": "Deck", "ownerId": "player2"}
        ]
    }
    owner_id = "player1"
    
    # モックカードマスターデータ（TOカード）
    mock_card_masters = {
        "to_card1": {"name": "TO Card", "isTO": True, "toEffect": {"type": "heal", "value": 5}}
    }
    
    with patch('actions.process_damage.fetch_card_masters', return_value=mock_card_masters):
        events = handle_process_damage(card, act, item, owner_id)
    
    # 結果検証
    move_events = [e for e in events if e["type"] == "MoveZone"]
    select_events = [e for e in events if e["type"] == "SelectOption"]
    
    assert len(move_events) == 1
    assert len(select_events) == 1
    
    # SelectOptionイベントの検証
    select_event = select_events[0]
    assert select_event["payload"]["options"] == ["use", "not_use"]
    assert "choiceRequests" in item
    assert len(item["choiceRequests"]) == 1

def test_process_damage_reflection():
    """反射ダメージのテスト"""
    # テストデータ
    attacker_id = "player1"
    defender_id = "player2"
    damage_value = 3
    item = {
        "cards": [
            {
                "id": "field1",
                "zone": "Field",
                "ownerId": "player2",
                "statuses": [{"key": "IsChainPainReflect", "value": 1}]
            }
        ]
    }
    
    events = check_reflection_damage(attacker_id, defender_id, damage_value, item)
    
    # 結果検証
    assert len(events) == 2
    
    # ReflectionDamageイベントの検証
    reflection_events = [e for e in events if e["type"] == "ReflectionDamage"]
    assert len(reflection_events) == 1
    assert reflection_events[0]["payload"]["attackerId"] == attacker_id
    assert reflection_events[0]["payload"]["defenderId"] == defender_id
    assert reflection_events[0]["payload"]["originalDamage"] == damage_value
    
    # ProcessDamageイベントの検証
    process_events = [e for e in events if e["type"] == "ProcessDamage"]
    assert len(process_events) == 1
    assert process_events[0]["payload"]["targetPlayerId"] == attacker_id
    assert process_events[0]["payload"]["isReflection"] == True

def test_to_selection_result_use():
    """TO使用選択結果のテスト"""
    # テストデータ
    damage_card = {"id": "card1", "cardId": "to_card1"}
    selected_value = "use"
    item = {}
    
    # モックカードマスターデータ
    mock_card_masters = {
        "to_card1": {"name": "TO Card", "isTO": True, "toEffect": {"type": "heal", "value": 5}}
    }
    
    with patch('actions.process_damage.fetch_card_masters', return_value=mock_card_masters):
        events = process_to_selection_result(damage_card, selected_value, item)
    
    # 結果検証
    assert len(events) == 2
    
    # AbilityActivatedイベントの検証
    ability_events = [e for e in events if e["type"] == "AbilityActivated"]
    assert len(ability_events) == 1
    assert ability_events[0]["payload"]["ability"] == "TO"
    
    # SelectOptionResultイベントの検証
    result_events = [e for e in events if e["type"] == "SelectOptionResult"]
    assert len(result_events) == 1
    assert result_events[0]["payload"]["selectedValue"] == "use"

def test_to_selection_result_not_use():
    """TO使用しない選択結果のテスト"""
    # テストデータ
    damage_card = {"id": "card1", "cardId": "to_card1"}
    selected_value = "not_use"
    item = {}
    
    # モックカードマスターデータ
    mock_card_masters = {
        "to_card1": {"name": "TO Card", "isTO": True, "availableColors": ["Red", "Blue"]}
    }
    
    with patch('actions.process_damage.fetch_card_masters', return_value=mock_card_masters):
        events = process_to_selection_result(damage_card, selected_value, item)
    
    # 結果検証
    assert len(events) == 2
    
    # AssignColorイベントの検証
    assign_events = [e for e in events if e["type"] == "AssignColor"]
    assert len(assign_events) == 1
    assert assign_events[0]["payload"]["color"] in ["Red", "Blue"]
    
    # SelectOptionResultイベントの検証
    result_events = [e for e in events if e["type"] == "SelectOptionResult"]
    assert len(result_events) == 1
    assert result_events[0]["payload"]["selectedValue"] == "not_use"

def test_process_damage_no_reflection():
    """反射ダメージなしのテスト"""
    # テストデータ
    attacker_id = "player1"
    defender_id = "player2"
    damage_value = 3
    item = {
        "cards": [
            {
                "id": "field1",
                "zone": "Field",
                "ownerId": "player2",
                "statuses": [{"key": "SomeOtherStatus", "value": 1}]
            }
        ]
    }
    
    events = check_reflection_damage(attacker_id, defender_id, damage_value, item)
    
    # 結果検証：反射ダメージはなし
    assert len(events) == 0