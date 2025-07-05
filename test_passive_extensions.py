# test_passive_extensions.py
# 簡単なテストケース例 - パッシブアビリティ対象拡張の動作確認

from lambda_function import evaluate_condition, _get_target_zones_from_action
from helper import get_target_cards, TARGET_ZONES

def test_zone_constants():
    """対象ゾーンリストの定数定義テスト"""
    expected_zones = [
        "Field", "Environment", "Counter", "Hand", 
        "Deck", "Graveyard", "ExileZone", "DamageZone"
    ]
    assert TARGET_ZONES == expected_zones
    print("✓ TARGET_ZONES constant defined correctly")

def test_environment_targeting():
    """Environmentゾーンのターゲティングテスト"""
    # テストデータ
    src = {"id": "leader1", "ownerId": "player1"}
    action = {"target": "Environment"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field"},
            {"id": "card2", "ownerId": "player1", "zone": "Environment"},
            {"id": "card3", "ownerId": "player2", "zone": "Environment"},
        ]
    }
    
    targets = get_target_cards(src, action, item)
    target_ids = [t["id"] for t in targets]
    
    expected = ["card2", "card3"]
    assert target_ids == expected
    print("✓ Environment zone targeting works correctly")

def test_counter_targeting():
    """Counterゾーンのターゲティングテスト"""
    src = {"id": "leader1", "ownerId": "player1"}
    action = {"target": "PlayerCounter"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Counter"},
            {"id": "card2", "ownerId": "player2", "zone": "Counter"},
        ]
    }
    
    targets = get_target_cards(src, action, item)
    target_ids = [t["id"] for t in targets]
    
    expected = ["card1"]
    assert target_ids == expected
    print("✓ Counter zone targeting works correctly")

def test_extended_conditions():
    """拡張された条件評価のテスト"""
    card = {"id": "leader1", "ownerId": "player1"}
    item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field"},
            {"id": "card2", "ownerId": "player2", "zone": "Field"},
            {"id": "card3", "ownerId": "player2", "zone": "Field"},
        ],
        "turnCount": 5
    }
    
    # EnemyFieldCount>=2 のテスト
    result = evaluate_condition("EnemyFieldCount>=2", card, item)
    assert result == True
    print("✓ EnemyFieldCount>=2 condition works correctly")
    
    # TurnCount>=3 のテスト
    result = evaluate_condition("TurnCount>=3", card, item)
    assert result == True
    print("✓ TurnCount>=3 condition works correctly")

def test_zone_detection():
    """ゾーン検出ヘルパーのテスト"""
    actions = [
        {"target": "Environment", "expected": ["Environment"]},
        {"target": "PlayerField", "expected": ["Field"]},
        {"target": "Counter", "expected": ["Counter"]},
    ]
    
    for action_data in actions:
        zones = _get_target_zones_from_action(action_data)
        assert zones == action_data["expected"]
    
    print("✓ Zone detection helper works correctly")

def run_all_tests():
    """すべてのテストを実行"""
    print("パッシブアビリティ対象拡張のテスト開始...")
    
    test_zone_constants()
    test_environment_targeting()
    test_counter_targeting()
    test_extended_conditions()
    test_zone_detection()
    
    print("✓ すべてのテストが成功しました！")

if __name__ == "__main__":
    run_all_tests()