# tests/test_transform_random.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.transform import handle_transform

def test_transform_with_selection_key():
    """selectionKey を使用した変身のテスト"""
    # テスト用のカード（変身する対象）
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
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
        "cards": [card],
        "choiceResponses": [
            {
                "requestId": "random_transform",
                "selectedValue": "new_card_id"
            }
        ]
    }
    
    # Transform アクションを実行
    events = handle_transform(card, act, item, "player1")
    
    # イベントが正しく生成されることを確認
    assert len(events) == 1
    assert events[0]["type"] == "Transform"
    assert events[0]["payload"]["cardId"] == "test_card"
    assert events[0]["payload"]["fromCardId"] == "original_card"
    assert events[0]["payload"]["toCardId"] == "new_card_id"
    assert events[0]["payload"]["resetStatuses"] is True
    assert events[0]["payload"]["resetPower"] is True
    assert events[0]["payload"]["resetDamage"] is True
    
    # カードが変身していることを確認
    assert card["baseCardId"] == "new_card_id"
    assert card["statuses"] == []  # リセットされている
    assert card["power"] == 1000   # デフォルト値
    assert card["damage"] == 0     # リセット

def test_transform_with_keyword():
    """keyword パラメータを使用した変身のテスト"""
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self",
        "keyword": "evolved_card"
    }
    
    item = {"cards": [card]}
    
    events = handle_transform(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["payload"]["toCardId"] == "evolved_card"
    assert card["baseCardId"] == "evolved_card"

def test_transform_with_options():
    """options パラメータを使用した変身のテスト"""
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self",
        "options": ["option1", "option2", "option3"]
    }
    
    item = {"cards": [card]}
    
    events = handle_transform(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["payload"]["toCardId"] == "option1"  # 最初の選択肢
    assert card["baseCardId"] == "option1"

def test_transform_priority_order():
    """変身先決定の優先順位テスト"""
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
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
        "cards": [card],
        "choiceResponses": [
            {
                "requestId": "selection_key",
                "selectedValue": "selected_card"
            }
        ]
    }
    
    events = handle_transform(card, act, item, "player1")
    
    # selectionKey が最優先で使用される
    assert events[0]["payload"]["toCardId"] == "selected_card"

def test_transform_no_target():
    """変身先が指定されていない場合のテスト"""
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
        "statuses": [],
        "tempStatuses": []
    }
    
    act = {
        "type": "Transform",
        "target": "Self"
    }
    
    item = {"cards": [card]}
    
    events = handle_transform(card, act, item, "player1")
    
    # 変身先が指定されていない場合は何もしない
    assert len(events) == 0


def test_transform_selectionkey_with_empty_target_fallback():
    """selectionKey が指定されているが target が空の場合のテスト（フォールバック動作）"""
    card = {
        "id": "test_card",
        "ownerId": "player1",
        "zone": "Field",
        "baseCardId": "original_card",
        "statuses": [],
        "tempStatuses": []
    }
    
    # Unity のログのように target が空の場合をシミュレート
    act = {
        "type": "Transform",
        "target": "",  # 空文字
        "selectionKey": "RandomSelectKey"
    }
    
    item = {
        "cards": [card],
        "choiceResponses": [
            {
                "requestId": "RandomSelectKey",
                "selectedValue": "token_002"
            }
        ]
    }
    
    events = handle_transform(card, act, item, "player1")
    
    # target が空でも selectionKey があれば変身は実行されない（現在の実装）
    # この場合、resolve_targets が空の配列を返すため、変身は実行されない
    assert len(events) == 0