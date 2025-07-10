# tests/test_random_actions.py
import pytest
import json
import random
from unittest.mock import patch
from actions.select_option import handle_select_option
from actions.transform import handle_transform
from actions.create_token import handle_create_token


def test_select_option_random_mode():
    """SelectOption アクションの重み付きランダム選択テスト"""
    # テストデータの準備
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002", "token_003"],
        "weights": ["10", "40", "30"],
        "selectionKey": "RandomSelectKey"
    }
    item = {"choiceResponses": []}
    
    # randomをモック
    with patch('random.choices', return_value=["token_002"]):
        events = handle_select_option(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert events[0]["payload"]["selectedValue"] == "token_002"
    assert events[0]["payload"]["selectionKey"] == "RandomSelectKey"
    
    # choiceResponsesに自動追加されているか確認
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["requestId"] == "RandomSelectKey"
    assert item["choiceResponses"][0]["selectedValue"] == "token_002"


def test_select_option_random_mode_no_weights():
    """SelectOption アクションの均等ランダム選択テスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002", "token_003"],
        "selectionKey": "RandomSelectKey"
    }
    item = {"choiceResponses": []}
    
    # randomをモック
    with patch('random.choice', return_value="token_001"):
        events = handle_select_option(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert events[0]["payload"]["selectedValue"] == "token_001"
    
    # choiceResponsesに自動追加されているか確認
    assert len(item["choiceResponses"]) == 1
    assert item["choiceResponses"][0]["selectedValue"] == "token_001"


def test_transform_with_selection_key():
    """Transform アクションの選択キー対応テスト"""
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
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "Transform"
    assert events[0]["payload"]["fromCardId"] == "original_card"
    assert events[0]["payload"]["toCardId"] == "token_002"
    
    # カードのbaseCardIdが変更されているか確認
    assert item["cards"][0]["baseCardId"] == "token_002"


def test_create_token_with_random_selection():
    """CreateToken アクションの重み付きランダム選択テスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "CreateToken",
        "tokenBaseIds": ["token_001", "token_002", "token_003"],
        "weights": ["10", "40", "30"],
        "target": "Field",
        "value": "2"
    }
    item = {"cards": []}
    
    # randomをモック
    with patch('random.choices', return_value=["token_002"]):
        events = handle_create_token(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 2  # 2つのトークンが生成される
    assert all(event["type"] == "CreateToken" for event in events)
    assert all(event["payload"]["baseCardId"] == "token_002" for event in events)
    assert all(event["payload"]["ownerId"] == "player1" for event in events)
    
    # itemのcardsに追加されているか確認
    assert len(item["cards"]) == 2
    assert all(card["baseCardId"] == "token_002" for card in item["cards"])
    assert all(card["ownerId"] == "player1" for card in item["cards"])


def test_create_token_with_random_selection_no_weights():
    """CreateToken アクションの均等ランダム選択テスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "CreateToken",
        "tokenBaseIds": ["token_001", "token_002", "token_003"],
        "target": "Field",
        "value": "1"
    }
    item = {"cards": []}
    
    # randomをモック
    with patch('random.choice', return_value="token_001"):
        events = handle_create_token(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "CreateToken"
    assert events[0]["payload"]["baseCardId"] == "token_001"
    
    # itemのcardsに追加されているか確認
    assert len(item["cards"]) == 1
    assert item["cards"][0]["baseCardId"] == "token_001"


def test_select_option_client_mode():
    """SelectOption アクションのクライアントモードテスト（従来の動作）"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "client",
        "options": ["token_001", "token_002", "token_003"],
        "weights": ["10", "40", "30"],
        "selectionKey": "ClientSelectKey"
    }
    item = {"choiceResponses": []}
    
    events = handle_select_option(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert "selectedValue" not in events[0]["payload"]  # 選択されていない
    assert events[0]["payload"]["options"] == ["token_001", "token_002", "token_003"]
    assert events[0]["payload"]["weights"] == ["10", "40", "30"]
    
    # choiceResponsesに自動追加されていないか確認
    assert len(item["choiceResponses"]) == 0


def test_transform_fallback_to_keyword():
    """Transform アクションの keyword フォールバックテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "Transform",
        "target": "Self",
        "keyword": "fallback_card"
    }
    item = {
        "cards": [{"id": "test_card", "ownerId": "player1", "baseCardId": "original_card"}],
        "choiceResponses": []
    }
    
    events = handle_transform(card, act, item, "player1")
    
    # 結果の検証
    assert len(events) == 1
    assert events[0]["type"] == "Transform"
    assert events[0]["payload"]["toCardId"] == "fallback_card"
    
    # カードのbaseCardIdが変更されているか確認
    assert item["cards"][0]["baseCardId"] == "fallback_card"