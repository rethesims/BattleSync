# tests/test_process_damage.py
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.process_damage import handle_process_damage, _assign_random_color, _check_reflection_damage

def test_basic_damage_card_movement():
    """基本的なダメージカード移動のテスト"""
    # セットアップ
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 2,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "deck_001", "ownerId": "player2", "zone": "Deck", "name": "Test Card 1"},
            {"id": "deck_002", "ownerId": "player2", "zone": "Deck", "name": "Test Card 2"},
            {"id": "deck_003", "ownerId": "player2", "zone": "Deck", "name": "Test Card 3"}
        ],
        "choiceResponses": []
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "deck_001": {"isTO": False, "availableColors": ["Red", "Blue"]},
            "deck_002": {"isTO": False, "availableColors": ["Green", "Yellow"]}
        }
        
        with patch('actions.process_damage.random.choice') as mock_choice:
            mock_choice.return_value = "Red"
            
            # 実行
            events = handle_process_damage(card, act, item, owner_id)
            
            # 検証
            # カードがダメージゾーンに移動していることを確認
            assert item["cards"][0]["zone"] == "DamageZone"
            assert item["cards"][1]["zone"] == "DamageZone"
            assert item["cards"][2]["zone"] == "Deck"  # 3枚目は移動しない
            
            # MoveZoneイベントが2つ生成されていることを確認
            move_events = [e for e in events if e["type"] == "MoveZone"]
            assert len(move_events) == 2
            assert move_events[0]["payload"]["cardId"] == "deck_001"
            assert move_events[0]["payload"]["fromZone"] == "Deck"
            assert move_events[0]["payload"]["toZone"] == "DamageZone"
            
            # AssignColorイベントが2つ生成されていることを確認
            color_events = [e for e in events if e["type"] == "AssignColor"]
            assert len(color_events) == 2
            
            # OnDamageトリガーが発生していることを確認
            trigger_events = [e for e in events if e["type"] == "AbilityActivated"]
            assert len(trigger_events) == 1
            assert trigger_events[0]["payload"]["trigger"] == "OnDamage"

def test_to_card_use_scenario():
    """TO「使う」シナリオのテスト"""
    # セットアップ
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 1,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "to_card_001", "ownerId": "player2", "zone": "Deck", "name": "Transform Stone"}
        ],
        "choiceResponses": [
            {
                "requestId": "to_choice_to_card_001",
                "playerId": "player2",
                "selectedValue": "use"
            }
        ]
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "to_card_001": {
                "isTO": True,
                "toEffect": {
                    "type": "Transform",
                    "target": "Self",
                    "transformTo": "evolved_card_001"
                }
            }
        }
        
        # 実行
        events = handle_process_damage(card, act, item, owner_id)
        
        # 検証
        # カードがダメージゾーンに移動していることを確認
        assert item["cards"][0]["zone"] == "DamageZone"
        
        # AbilityActivatedイベント（TO効果）が生成されていることを確認
        ability_events = [e for e in events if e["type"] == "AbilityActivated"]
        to_events = [e for e in ability_events if e["payload"].get("trigger") == "ToEffect"]
        assert len(to_events) == 1
        assert to_events[0]["payload"]["sourceCardId"] == "to_card_001"
        
        # SelectOptionResultイベントが生成されていることを確認
        result_events = [e for e in events if e["type"] == "SelectOptionResult"]
        assert len(result_events) == 1
        assert result_events[0]["payload"]["selectedValue"] == "use"
        
        # 使用済みレスポンスが削除されていることを確認
        assert len(item["choiceResponses"]) == 0

def test_to_card_not_use_scenario():
    """TO「使わない」+カラー付与シナリオのテスト"""
    # セットアップ
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 1,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "to_card_001", "ownerId": "player2", "zone": "Deck", "name": "Transform Stone"}
        ],
        "choiceResponses": [
            {
                "requestId": "to_choice_to_card_001",
                "playerId": "player2",
                "selectedValue": "not_use"
            }
        ]
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "to_card_001": {
                "isTO": True,
                "availableColors": ["Blue", "Green"]
            }
        }
        
        with patch('actions.process_damage.random.choice') as mock_choice:
            mock_choice.return_value = "Blue"
            
            # 実行
            events = handle_process_damage(card, act, item, owner_id)
            
            # 検証
            # カードがダメージゾーンに移動していることを確認
            assert item["cards"][0]["zone"] == "DamageZone"
            
            # AssignColorイベントが生成されていることを確認
            color_events = [e for e in events if e["type"] == "AssignColor"]
            assert len(color_events) == 1
            assert color_events[0]["payload"]["cardId"] == "to_card_001"
            assert color_events[0]["payload"]["color"] == "Blue"
            
            # カードにカラーステータスが追加されていることを確認
            card_statuses = item["cards"][0].get("statuses", [])
            color_status = next((s for s in card_statuses if s["key"] == "ColorCost_Blue"), None)
            assert color_status is not None
            assert color_status["value"] == 1
            
            # SelectOptionResultイベントが生成されていることを確認
            result_events = [e for e in events if e["type"] == "SelectOptionResult"]
            assert len(result_events) == 1
            assert result_events[0]["payload"]["selectedValue"] == "not_use"

def test_reflection_damage_chain():
    """反射ダメージチェインのテスト"""
    # セットアップ
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 2,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "deck_001", "ownerId": "player2", "zone": "Deck", "name": "Test Card 1"},
            {"id": "deck_002", "ownerId": "player2", "zone": "Deck", "name": "Test Card 2"},
            {"id": "field_001", "ownerId": "player2", "zone": "Field", "name": "Reflection Card",
             "statuses": [{"key": "IsChainPainReflect", "value": 1}]}
        ],
        "choiceResponses": []
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "deck_001": {"isTO": False},
            "deck_002": {"isTO": False}
        }
        
        with patch('actions.process_damage.random.choice') as mock_choice:
            mock_choice.return_value = "Red"
            
            # 実行
            events = handle_process_damage(card, act, item, owner_id)
            
            # 検証
            # 反射ダメージイベントが生成されていることを確認
            reflection_events = [e for e in events if e["type"] == "ReflectionDamage"]
            assert len(reflection_events) == 1
            assert reflection_events[0]["payload"]["sourceCardId"] == "field_001"
            assert reflection_events[0]["payload"]["targetPlayerId"] == "player1"
            assert reflection_events[0]["payload"]["damageCount"] == 2
            
            # ProcessDamageイベント（反射）が生成されていることを確認
            process_events = [e for e in events if e["type"] == "ProcessDamage"]
            assert len(process_events) == 1
            assert process_events[0]["payload"]["targetPlayerId"] == "player1"
            assert process_events[0]["payload"]["value"] == 2
            assert process_events[0]["payload"]["isReflection"] == True

def test_on_damage_trigger():
    """OnDamageトリガーのテスト"""
    # セットアップ
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 1,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "deck_001", "ownerId": "player2", "zone": "Deck", "name": "Test Card 1"}
        ],
        "choiceResponses": []
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "deck_001": {"isTO": False}
        }
        
        with patch('actions.process_damage.random.choice') as mock_choice:
            mock_choice.return_value = "Red"
            
            # 実行
            events = handle_process_damage(card, act, item, owner_id)
            
            # 検証
            # OnDamageトリガーが発生していることを確認
            trigger_events = [e for e in events if e["type"] == "AbilityActivated"]
            on_damage_events = [e for e in trigger_events if e["payload"].get("trigger") == "OnDamage"]
            assert len(on_damage_events) == 1
            assert on_damage_events[0]["payload"]["sourceCardId"] == "attacker_001"
            assert on_damage_events[0]["payload"]["targetPlayerId"] == "player2"
            assert on_damage_events[0]["payload"]["damageCount"] == 1

def test_assign_random_color():
    """ランダムカラー付与のテスト"""
    card = {"id": "test_card"}
    
    # 利用可能なカラーが指定されている場合
    master_data = {"availableColors": ["Red", "Blue"]}
    with patch('actions.process_damage.random.choice') as mock_choice:
        mock_choice.return_value = "Red"
        color = _assign_random_color(card, master_data)
        assert color == "Red"
        mock_choice.assert_called_with(["Red", "Blue"])
    
    # 利用可能なカラーが指定されていない場合
    master_data = {}
    with patch('actions.process_damage.random.choice') as mock_choice:
        mock_choice.return_value = "Green"
        color = _assign_random_color(card, master_data)
        assert color == "Green"
        mock_choice.assert_called_with(["Red", "Blue", "Green", "Yellow"])

def test_no_deck_cards():
    """デッキにカードがない場合のテスト"""
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 2,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [],  # デッキにカードがない
        "choiceResponses": []
    }
    owner_id = "player1"
    
    # 実行
    events = handle_process_damage(card, act, item, owner_id)
    
    # 検証
    # 空のイベントリストが返されることを確認
    assert events == []

def test_to_card_no_response():
    """TOカードの選択がまだされていない場合のテスト"""
    card = {"id": "attacker_001", "ownerId": "player1"}
    act = {
        "type": "ProcessDamage",
        "value": 1,
        "targetPlayerId": "player2"
    }
    item = {
        "cards": [
            {"id": "to_card_001", "ownerId": "player2", "zone": "Deck", "name": "Transform Stone"}
        ],
        "choiceResponses": []  # まだ選択されていない
    }
    owner_id = "player1"
    
    # モックsetup
    with patch('actions.process_damage.fetch_card_masters') as mock_fetch:
        mock_fetch.return_value = {
            "to_card_001": {"isTO": True}
        }
        
        # 実行
        events = handle_process_damage(card, act, item, owner_id)
        
        # 検証
        # SelectOptionイベントが生成されていることを確認
        select_events = [e for e in events if e["type"] == "SelectOption"]
        assert len(select_events) == 1
        assert select_events[0]["payload"]["selectionKey"] == "to_choice_to_card_001"
        assert select_events[0]["payload"]["options"] == ["use", "not_use"]
        
        # choiceRequestsに追加されていることを確認
        assert len(item["choiceRequests"]) == 1
        assert item["choiceRequests"][0]["requestId"] == "to_choice_to_card_001"
        assert item["choiceRequests"][0]["playerId"] == "player2"