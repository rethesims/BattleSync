#!/usr/bin/env python3
"""
ランダム変身・トークン生成機能の実装テスト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from actions.select_option import handle_select_option
from actions.transform import handle_transform
from actions.create_token import handle_create_token
from lambda_function import handle_trigger, apply_action
import random

def test_select_option_random():
    """SelectOption のランダム選択テスト"""
    print("Testing SelectOption random mode...")
    
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002", "token_003"],
        "weights": ["10", "40", "30"],
        "selectionKey": "RandomSelectKey"
    }
    item = {"choiceResponses": []}
    
    # ランダムシードを固定
    random.seed(42)
    
    events = handle_select_option(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert "selectedValue" in events[0]["payload"]
    assert events[0]["payload"]["selectedValue"] in ["token_001", "token_002", "token_003"]
    
    # choiceResponsesに自動追加されているか確認
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["requestId"] == "RandomSelectKey"
    
    print("✓ SelectOption random mode test passed")

def test_transform_with_selection():
    """Transform のselectionKey対応テスト"""
    print("Testing Transform with selectionKey...")
    
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "Transform",
        "target": "Self",
        "selectionKey": "RandomSelectKey"
    }
    item = {
        "cards": [{"id": "test_card", "ownerId": "player1", "baseCardId": "original_card"}],
        "choiceResponses": [
            {"requestId": "RandomSelectKey", "selectedValue": "token_002"}
        ]
    }
    
    events = handle_transform(card, act, item, "player1")
    
    assert len(events) == 1
    assert events[0]["type"] == "Transform"
    assert events[0]["payload"]["fromCardId"] == "original_card"
    assert events[0]["payload"]["toCardId"] == "token_002"
    
    # カードのbaseCardIdが変更されているか確認
    assert item["cards"][0]["baseCardId"] == "token_002"
    
    print("✓ Transform with selectionKey test passed")

def test_create_token_random():
    """CreateToken のランダム選択テスト"""
    print("Testing CreateToken random selection...")
    
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "CreateToken",
        "tokenBaseIds": ["token_001", "token_002", "token_003"],
        "weights": ["10", "40", "30"],
        "target": "Field",
        "value": "2"
    }
    item = {"cards": []}
    
    # ランダムシードを固定
    random.seed(42)
    
    events = handle_create_token(card, act, item, "player1")
    
    assert len(events) == 2  # 2つのトークンが生成される
    assert all(event["type"] == "CreateToken" for event in events)
    assert all(event["payload"]["baseCardId"] in ["token_001", "token_002", "token_003"] for event in events)
    
    # itemのcardsに追加されているか確認
    assert len(item["cards"]) == 2
    assert all(card["baseCardId"] in ["token_001", "token_002", "token_003"] for card in item["cards"])
    
    print("✓ CreateToken random selection test passed")

def test_integration_flow():
    """SelectOption → Transform の統合テスト"""
    print("Testing integration flow...")
    
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
    
    # ランダムシードを固定
    random.seed(42)
    
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
    assert select_event is not None
    assert "selectedValue" in select_event["payload"]
    
    # 変身結果の確認
    transform_event = next((e for e in events if e["type"] == "Transform"), None)
    assert transform_event is not None
    assert transform_event["payload"]["fromCardId"] == "cocoon_card"
    assert transform_event["payload"]["toCardId"] == select_event["payload"]["selectedValue"]
    
    # 最終的なカードの状態確認
    assert card["baseCardId"] == select_event["payload"]["selectedValue"]
    
    print("✓ Integration flow test passed")

def main():
    """メインテスト実行"""
    print("Running random implementation tests...")
    print("=" * 50)
    
    try:
        test_select_option_random()
        test_transform_with_selection()
        test_create_token_random()
        test_integration_flow()
        
        print("=" * 50)
        print("All tests passed successfully! 🎉")
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()