#!/usr/bin/env python3
"""
test_sourceid_fix.py
sourceId設定修正のテストファイル
"""

import json
from unittest.mock import Mock
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lambda_function import apply_passive_effect, clear_passive_from_targets
from actions.battle_buff import handle as battle_buff_handle
from actions.aura import handle_power_aura, handle_damage_aura
from helper import add_temp_status


def test_sourceid_setting():
    """
    sourceId設定が正しく動作することを確認
    """
    print("=== sourceId設定テスト ===")
    
    # テスト用のカード
    test_card = {
        "id": "card-123",
        "ownerId": "player-1",
        "tempStatuses": []
    }
    
    # テスト用のアクション（sourceCardIdを含む）
    test_action = {
        "type": "BattleBuff",
        "keyword": "Power",
        "value": 5,
        "duration": 3,
        "sourceCardId": "leader-456"
    }
    
    # テスト用のitem
    test_item = {
        "turnCount": 5
    }
    
    # battle_buffハンドラを呼び出し
    events = battle_buff_handle(test_card, test_action, test_item)
    
    # tempStatusesにsourceIdが設定されているかチェック
    temp_statuses = test_card.get("tempStatuses", [])
    assert len(temp_statuses) == 1, f"Expected 1 tempStatus, got {len(temp_statuses)}"
    
    temp_status = temp_statuses[0]
    assert temp_status["sourceId"] == "leader-456", f"Expected sourceId 'leader-456', got '{temp_status['sourceId']}'"
    
    print(f"✅ tempStatus設定成功: {temp_status}")
    
    # PowerAura/DamageAuraのテスト
    print("\n=== PowerAura/DamageAuraテスト ===")
    
    # PowerAuraテスト
    power_card = {
        "id": "power-card-789",
        "ownerId": "player-1",
        "tempStatuses": []
    }
    
    power_action = {
        "type": "PowerAura",
        "target": "Self",
        "value": 3,
        "duration": -1
    }
    
    power_events = handle_power_aura(power_card, power_action, test_item, "player-1")
    
    # PowerAuraのsourceIdはカード自身のID
    power_temp_statuses = power_card.get("tempStatuses", [])
    assert len(power_temp_statuses) == 1, f"Expected 1 PowerAura tempStatus, got {len(power_temp_statuses)}"
    
    power_temp_status = power_temp_statuses[0]
    assert power_temp_status["sourceId"] == "power-card-789", f"Expected sourceId 'power-card-789', got '{power_temp_status['sourceId']}'"
    
    print(f"✅ PowerAura設定成功: {power_temp_status}")
    
    # パッシブ効果のシミュレーション
    print("\n=== パッシブ効果シミュレーション ===")
    
    # テスト用のプレイヤー
    test_player = {
        "id": "player-1",
        "leaderId": "leader-999",
        "field": [{"id": "field-card-1", "ownerId": "player-1", "tempStatuses": []}]
    }
    
    # テスト用のpassive effect
    test_effect = {
        "condition": "",
        "actions": [{
            "type": "BattleBuff",
            "target": "PlayerField",
            "keyword": "Power",
            "value": 2,
            "duration": 1
        }]
    }
    
    # テスト用のitem（フィールドカード情報を含む）
    test_item_with_field = {
        "turnCount": 1,
        "players": [test_player]
    }
    
    # apply_passive_effectを呼び出し
    events = []
    apply_passive_effect(test_effect, test_player, test_item_with_field, events)
    
    # フィールドカードのtempStatusesをチェック
    field_card = test_player["field"][0]
    field_temp_statuses = field_card.get("tempStatuses", [])
    
    if len(field_temp_statuses) > 0:
        field_temp_status = field_temp_statuses[0]
        print(f"✅ パッシブ効果設定成功: {field_temp_status}")
        
        # sourceIdがリーダーのIDになっているかチェック
        assert field_temp_status["sourceId"] == "leader-999", f"Expected sourceId 'leader-999', got '{field_temp_status['sourceId']}'"
        print(f"✅ sourceId正しく設定: {field_temp_status['sourceId']}")
    else:
        print("⚠️ フィールドカードにtempStatusが設定されていません")
    
    print("\n=== テスト完了 ===")


if __name__ == "__main__":
    test_sourceid_setting()