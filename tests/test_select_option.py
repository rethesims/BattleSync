# tests/test_select_option.py
import pytest
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions.select_option import handle_select_option
from helper import weighted_random_select

def test_weighted_random_select():
    """重み付きランダム選択のテスト"""
    # 基本的な重み付き選択
    options = ["A", "B", "C"]
    weights = [10, 30, 60]
    
    # 100回実行して結果を確認
    results = {}
    for _ in range(100):
        result = weighted_random_select(options, weights)
        results[result] = results.get(result, 0) + 1
    
    # 全ての選択肢が選ばれることを確認
    assert "A" in results
    assert "B" in results
    assert "C" in results
    
    # 重みが高い方が多く選ばれることを確認（統計的テスト）
    assert results["C"] > results["A"]  # 重み60 > 重み10

def test_handle_select_option_server_side():
    """サーバー側ランダム選択のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": ["token_001", "token_002", "token_003"],
        "weights": [10, 40, 50],
        "selectionKey": "test_key"
    }
    item = {"choiceResponses": []}
    owner_id = "player1"
    
    # Mock weighted_random_select to return predictable result
    with patch('actions.select_option.weighted_random_select') as mock_select:
        mock_select.return_value = "token_002"
        
        events = handle_select_option(card, act, item, owner_id)
        
        # イベントが正しく生成されることを確認
        assert len(events) == 1
        assert events[0]["type"] == "SelectOption"
        assert events[0]["payload"]["selectedValue"] == "token_002"
        assert events[0]["payload"]["selectionKey"] == "test_key"
        
        # choiceResponses に追加されることを確認
        assert len(item["choiceResponses"]) == 1
        assert item["choiceResponses"][0]["requestId"] == "test_key"
        assert item["choiceResponses"][0]["selectedValue"] == "token_002"
        assert item["choiceResponses"][0]["playerId"] == "player1"

def test_handle_select_option_client_side():
    """クライアント側選択のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "client",
        "options": ["option1", "option2"],
        "weights": [30, 70],
        "selectionKey": "test_key"
    }
    item = {"choiceResponses": []}
    owner_id = "player1"
    
    events = handle_select_option(card, act, item, owner_id)
    
    # イベントが正しく生成されることを確認
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert events[0]["payload"]["selectionKey"] == "test_key"
    assert events[0]["payload"]["options"] == ["option1", "option2"]
    assert events[0]["payload"]["weights"] == [30, 70]
    
    # choiceResponses には追加されないことを確認
    assert len(item["choiceResponses"]) == 0

def test_handle_select_option_empty_options():
    """選択肢が空の場合のテスト"""
    card = {"id": "test_card", "ownerId": "player1"}
    act = {
        "type": "SelectOption",
        "mode": "random",
        "options": [],
        "selectionKey": "test_key"
    }
    item = {"choiceResponses": []}
    owner_id = "player1"
    
    events = handle_select_option(card, act, item, owner_id)
    
    # エラーイベントが生成されることを確認
    assert len(events) == 1
    assert events[0]["type"] == "SelectOption"
    assert events[0]["payload"]["selectedOption"] is None
    assert "選択肢がありません" in events[0]["payload"]["prompt"]

def test_weighted_random_select_edge_cases():
    """重み付きランダム選択のエッジケーステスト"""
    # 空の選択肢
    assert weighted_random_select([], []) == ""
    
    # 重みの数が一致しない
    assert weighted_random_select(["A"], []) == ""
    assert weighted_random_select(["A", "B"], [10]) == ""
    
    # 重みが0以下
    assert weighted_random_select(["A"], [0]) == ""
    assert weighted_random_select(["A"], [-1]) == ""
    
    # 単一の選択肢
    assert weighted_random_select(["A"], [10]) == "A"