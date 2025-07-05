#!/usr/bin/env python3
"""
パッシブアビリティの PowerAura/DamageAura 修正をテストする
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import apply_passive_effect, clear_passive_from_targets
from helper import keyword_map

def test_power_aura_temp_status():
    """PowerAura が TempPowerBoost を tempStatuses に設定することをテスト"""
    print("Testing PowerAura -> TempPowerBoost in tempStatuses...")
    
    # テストデータ
    player = {"id": "player1", "leaderId": "leader1"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
            {"id": "card2", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
            {"id": "card3", "ownerId": "player2", "zone": "Field", "tempStatuses": []},
        ]
    }
    
    effect = {
        "actions": [
            {
                "type": "PowerAura",
                "target": "PlayerField",
                "value": 2
            }
        ]
    }
    
    events = []
    apply_passive_effect(effect, player, item, events)
    
    # 確認
    player_cards = [c for c in item["cards"] if c["ownerId"] == "player1" and c["zone"] == "Field"]
    for card in player_cards:
        temp_statuses = card.get("tempStatuses", [])
        power_boosts = [s for s in temp_statuses if s["key"] == "TempPowerBoost"]
        print(f"Card {card['id']}: {len(power_boosts)} TempPowerBoost statuses")
        assert len(power_boosts) == 1, f"Expected 1 TempPowerBoost, got {len(power_boosts)}"
        assert power_boosts[0]["value"] == "2", f"Expected value '2', got {power_boosts[0]['value']}"
        assert power_boosts[0]["sourceId"] == "leader1", f"Expected sourceId 'leader1', got {power_boosts[0]['sourceId']}"
    
    print("✓ PowerAura correctly sets TempPowerBoost in tempStatuses")

def test_damage_aura_temp_status():
    """DamageAura が TempDamageBoost を tempStatuses に設定することをテスト"""
    print("Testing DamageAura -> TempDamageBoost in tempStatuses...")
    
    # テストデータ
    player = {"id": "player1", "leaderId": "leader1"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
            {"id": "card2", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
        ]
    }
    
    effect = {
        "actions": [
            {
                "type": "DamageAura",
                "target": "PlayerField",
                "value": 3
            }
        ]
    }
    
    events = []
    apply_passive_effect(effect, player, item, events)
    
    # 確認
    player_cards = [c for c in item["cards"] if c["ownerId"] == "player1" and c["zone"] == "Field"]
    for card in player_cards:
        temp_statuses = card.get("tempStatuses", [])
        damage_boosts = [s for s in temp_statuses if s["key"] == "TempDamageBoost"]
        print(f"Card {card['id']}: {len(damage_boosts)} TempDamageBoost statuses")
        assert len(damage_boosts) == 1, f"Expected 1 TempDamageBoost, got {len(damage_boosts)}"
        assert damage_boosts[0]["value"] == "3", f"Expected value '3', got {damage_boosts[0]['value']}"
        assert damage_boosts[0]["sourceId"] == "leader1", f"Expected sourceId 'leader1', got {damage_boosts[0]['sourceId']}"
    
    print("✓ DamageAura correctly sets TempDamageBoost in tempStatuses")

def test_player_field_targeting():
    """PlayerField ターゲットが正しく動作することをテスト"""
    print("Testing PlayerField targeting...")
    
    # テストデータ
    player = {"id": "player1", "leaderId": "leader1"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
            {"id": "card2", "ownerId": "player1", "zone": "Field", "tempStatuses": []},
            {"id": "card3", "ownerId": "player1", "zone": "Hand", "tempStatuses": []},  # 手札は対象外
            {"id": "card4", "ownerId": "player2", "zone": "Field", "tempStatuses": []},  # 相手は対象外
        ]
    }
    
    effect = {
        "actions": [
            {
                "type": "PowerAura",
                "target": "PlayerField",
                "value": 1
            }
        ]
    }
    
    events = []
    apply_passive_effect(effect, player, item, events)
    
    # 確認
    target_cards = [c for c in item["cards"] if c["ownerId"] == "player1" and c["zone"] == "Field"]
    non_target_cards = [c for c in item["cards"] if not (c["ownerId"] == "player1" and c["zone"] == "Field")]
    
    # 対象カードには効果が適用されている
    for card in target_cards:
        temp_statuses = card.get("tempStatuses", [])
        power_boosts = [s for s in temp_statuses if s["key"] == "TempPowerBoost"]
        print(f"Target card {card['id']}: {len(power_boosts)} TempPowerBoost statuses")
        assert len(power_boosts) == 1, f"Expected 1 TempPowerBoost on target card, got {len(power_boosts)}"
    
    # 非対象カードには効果が適用されていない
    for card in non_target_cards:
        temp_statuses = card.get("tempStatuses", [])
        power_boosts = [s for s in temp_statuses if s["key"] == "TempPowerBoost"]
        print(f"Non-target card {card['id']}: {len(power_boosts)} TempPowerBoost statuses")
        assert len(power_boosts) == 0, f"Expected 0 TempPowerBoost on non-target card, got {len(power_boosts)}"
    
    print("✓ PlayerField targeting works correctly")

def test_keyword_mapping():
    """キーワードマッピングが正しく動作することをテスト"""
    print("Testing keyword mapping...")
    
    assert keyword_map("Power") == "TempPowerBoost", f"Expected 'TempPowerBoost', got {keyword_map('Power')}"
    assert keyword_map("Damage") == "TempDamageBoost", f"Expected 'TempDamageBoost', got {keyword_map('Damage')}"
    
    print("✓ Keyword mapping works correctly")

if __name__ == "__main__":
    print("Running PowerAura/DamageAura fix tests...")
    test_keyword_mapping()
    test_power_aura_temp_status()
    test_damage_aura_temp_status()
    test_player_field_targeting()
    print("\n✅ All tests passed!")