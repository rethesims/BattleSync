# test_select_destroy_choiceRequests_flow.py
import pytest
import json
from unittest.mock import MagicMock

def test_select_destroy_choiceRequests_flow():
    """
    新しい choiceRequests/choiceResponses フローを使った Select→Destroy テスト
    1. Select時に choiceRequests が登録される
    2. submitChoiceResponse呼び出しで Destroy イベントが発生
    3. pendingDeferred / choiceRequests / choiceResponses が適切にクリアされる
    """
    # Lambda関数をimport
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lambda_function import handle_trigger, lambda_handler
    
    # テストデータセットアップ
    test_item = {
        "id": "test-match",
        "matchVersion": 0,
        "cards": [
            {"id": "source-card", "ownerId": "player1", "zone": "Field", 
             "effectList": [
                 {
                     "trigger": "OnSummon",
                     "actions": [
                         {
                             "type": "Select",
                             "target": "EnemyField", 
                             "selectionKey": "destroyTarget",
                             "mode": "single",
                             "prompt": "破壊対象を選択してください"
                         },
                         {
                             "type": "Destroy",
                             "selectionKey": "destroyTarget",
                             "deferred": True
                         }
                     ]
                 }
             ]},
            {"id": "target1", "ownerId": "player2", "zone": "Field"},
            {"id": "target2", "ownerId": "player2", "zone": "Field"}
        ],
        "choiceRequests": [],
        "choiceResponses": [],
        "pendingDeferred": []
    }
    
    # Step 1: handle_trigger を呼び出してSelect処理をテスト
    source_card = next(c for c in test_item["cards"] if c["id"] == "source-card")
    events = handle_trigger(source_card, "OnSummon", test_item)
    
    # Select処理により choiceRequests が登録されることを確認
    assert len(test_item["choiceRequests"]) == 1
    choice_request = test_item["choiceRequests"][0]
    assert choice_request["requestId"] == "destroyTarget"
    assert choice_request["playerId"] == "player1"
    assert choice_request["promptText"] == "破壊対象を選択してください"
    
    # pendingDeferred に Destroy アクションが保存されることを確認
    assert len(test_item["pendingDeferred"]) == 1
    pending_action = test_item["pendingDeferred"][0]
    assert pending_action["type"] == "Destroy"
    assert pending_action["selectionKey"] == "destroyTarget"
    assert pending_action["sourceCardId"] == "source-card"
    
    # Step 2: クライアントからの選択応答をシミュレート
    choice_response = {
        "requestId": "destroyTarget",
        "playerId": "player1", 
        "selectedIds": ["target1"]
    }
    
    # lambda_handlerを使ってsubmitChoiceResponseをテスト
    mock_event = {
        "info": {"fieldName": "submitChoiceResponse"},
        "arguments": {
            "matchId": "test-match",
            "json": json.dumps(choice_response)
        }
    }
    
    # DynamoDBのモック
    with pytest.mock.patch('lambda_function.table') as mock_table:
        mock_table.get_item.return_value = {"Item": test_item}
        mock_table.put_item = MagicMock()
        
        result = lambda_handler(mock_event, None)
    
    # Step 3: 結果を検証
    # Destroy イベントが返されることを確認
    assert "events" in result
    destroy_events = [e for e in result["events"] if e["type"] == "Destroy"]
    assert len(destroy_events) == 1
    assert destroy_events[0]["payload"]["cardId"] == "target1"
    assert destroy_events[0]["payload"]["toZone"] == "Graveyard"
    
    # pendingDeferred がクリアされることを確認
    updated_item = result["match"]
    assert len(updated_item.get("pendingDeferred", [])) == 0
    
    # choiceRequests と choiceResponses がクリアされることを確認  
    assert len(updated_item.get("choiceRequests", [])) == 0
    assert len(updated_item.get("choiceResponses", [])) == 0


def test_multiple_pending_deferred_actions():
    """
    複数のpendingDeferredアクションがある場合のテスト
    """
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lambda_function import lambda_handler
    
    # 複数のpendingDeferredアクションを持つテストデータ
    test_item = {
        "id": "test-match",
        "matchVersion": 0,
        "cards": [
            {"id": "target1", "ownerId": "player2", "zone": "Field"},
            {"id": "target2", "ownerId": "player2", "zone": "Field"},
            {"id": "target3", "ownerId": "player2", "zone": "Field"}
        ],
        "choiceRequests": [
            {
                "requestId": "destroyTarget",
                "playerId": "player1",
                "promptText": "破壊対象を選択してください"
            }
        ],
        "choiceResponses": [],
        "pendingDeferred": [
            {
                "type": "Destroy",
                "selectionKey": "destroyTarget",
                "sourceCardId": "source-card"
            },
            {
                "type": "Destroy", 
                "selectionKey": "otherTarget",
                "sourceCardId": "other-source"
            }
        ]
    }
    
    choice_response = {
        "requestId": "destroyTarget",
        "playerId": "player1",
        "selectedIds": ["target1"]
    }
    
    mock_event = {
        "info": {"fieldName": "submitChoiceResponse"},
        "arguments": {
            "matchId": "test-match",
            "json": json.dumps(choice_response)
        }
    }
    
    with pytest.mock.patch('lambda_function.table') as mock_table:
        mock_table.get_item.return_value = {"Item": test_item}
        mock_table.put_item = MagicMock()
        
        result = lambda_handler(mock_event, None)
    
    # 該当するselectionKeyのアクションのみが実行されることを確認
    updated_item = result["match"]
    remaining_pending = updated_item.get("pendingDeferred", [])
    assert len(remaining_pending) == 1
    assert remaining_pending[0]["selectionKey"] == "otherTarget"


def test_level_point_selection():
    """
    レベルポイント選択のテスト
    """
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lambda_function import handle_trigger, lambda_handler
    
    # テストデータセットアップ
    test_item = {
        "id": "test-match",
        "matchVersion": 0,
        "players": [
            {
                "id": "player1",
                "levelPoints": [
                    {"color": "RED", "isUsed": False},
                    {"color": "BLUE", "isUsed": True}
                ]
            },
            {
                "id": "player2",
                "levelPoints": [
                    {"color": "GREEN", "isUsed": False}
                ]
            }
        ],
        "cards": [
            {"id": "source-card", "ownerId": "player1", "zone": "Field", 
             "effectList": [
                 {
                     "trigger": "OnSummon",
                     "actions": [
                         {
                             "type": "Select",
                             "selectionType": "levelPoint",
                             "selectionKey": "levelPointTarget",
                             "mode": "single",
                             "prompt": "レベルポイントを選択してください"
                         },
                         {
                             "type": "ConsumeLevelPoint",
                             "selectionKey": "levelPointTarget",
                             "deferred": True
                         }
                     ]
                 }
             ]}
        ],
        "choiceRequests": [],
        "choiceResponses": [],
        "pendingDeferred": []
    }
    
    # Step 1: handle_trigger を呼び出してSelect処理をテスト
    source_card = next(c for c in test_item["cards"] if c["id"] == "source-card")
    events = handle_trigger(source_card, "OnSummon", test_item)
    
    # Select処理により choiceRequests が登録されることを確認
    assert len(test_item["choiceRequests"]) == 1
    choice_request = test_item["choiceRequests"][0]
    assert choice_request["requestId"] == "levelPointTarget"
    assert choice_request["playerId"] == "player1"
    assert choice_request["promptText"] == "レベルポイントを選択してください"
    assert choice_request["selectionType"] == "levelPoint"
    
    # レベルポイントの選択肢が正しく生成されることを確認
    expected_options = ["player1:RED", "player2:GREEN"]  # isUsed=Falseのもののみ
    assert set(choice_request["options"]) == set(expected_options)
    
    # pendingDeferred に ConsumeLevelPoint アクションが保存されることを確認
    assert len(test_item["pendingDeferred"]) == 1
    pending_action = test_item["pendingDeferred"][0]
    assert pending_action["type"] == "ConsumeLevelPoint"
    assert pending_action["selectionKey"] == "levelPointTarget"
    assert pending_action["selectionType"] == "levelPoint"


def test_optional_ability_activation():
    """
    オプション能力の発動確認テスト
    """
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lambda_function import handle_trigger, lambda_handler
    
    # テストデータセットアップ（オプション能力付き）
    test_item = {
        "id": "test-match",
        "matchVersion": 0,
        "cards": [
            {"id": "optional-card", "ownerId": "player1", "zone": "Field", 
             "effectList": [
                 {
                     "trigger": "OnSummon",
                     "optional": True,
                     "name": "破壊効果",
                     "actions": [
                         {
                             "type": "Select",
                             "target": "EnemyField",
                             "selectionKey": "optionalTarget",
                             "mode": "single",
                             "prompt": "破壊対象を選択してください"
                         },
                         {
                             "type": "Destroy",
                             "selectionKey": "optionalTarget",
                             "deferred": True
                         }
                     ]
                 }
             ]},
            {"id": "target1", "ownerId": "player2", "zone": "Field"}
        ],
        "choiceRequests": [],
        "choiceResponses": [],
        "pendingDeferred": []
    }
    
    # Step 1: handle_trigger を呼び出してオプション能力確認をテスト
    source_card = next(c for c in test_item["cards"] if c["id"] == "optional-card")
    events = handle_trigger(source_card, "OnSummon", test_item)
    
    # オプション能力の発動確認 choiceRequests が登録されることを確認
    assert len(test_item["choiceRequests"]) == 1
    choice_request = test_item["choiceRequests"][0]
    assert choice_request["playerId"] == "player1"
    assert "能力を発動しますか？" in choice_request["promptText"]
    assert "破壊効果" in choice_request["promptText"]
    assert choice_request["options"] == ["Yes", "No"]
    
    # pendingDeferred に効果全体が保存されることを確認
    assert len(test_item["pendingDeferred"]) == 1
    pending_effect = test_item["pendingDeferred"][0]
    assert pending_effect["effectType"] == "optionalAbility"
    assert pending_effect["sourceCardId"] == "optional-card"
    assert pending_effect["trigger"] == "OnSummon"
    assert len(pending_effect["actions"]) == 2
    
    # Step 2: "Yes" を選択した場合のテスト
    choice_response = {
        "requestId": choice_request["requestId"],
        "playerId": "player1",
        "selectedValue": "Yes"
    }
    
    mock_event = {
        "info": {"fieldName": "submitChoiceResponse"},
        "arguments": {
            "matchId": "test-match",
            "json": json.dumps(choice_response)
        }
    }
    
    with pytest.mock.patch('lambda_function.table') as mock_table:
        mock_table.get_item.return_value = {"Item": test_item}
        mock_table.put_item = MagicMock()
        
        result = lambda_handler(mock_event, None)
    
    # "Yes" を選択した場合、新しい choiceRequest が生成されることを確認
    updated_item = result["match"]
    assert len(updated_item.get("choiceRequests", [])) == 1
    new_choice_request = updated_item["choiceRequests"][0]
    assert new_choice_request["requestId"] == "optionalTarget"
    assert new_choice_request["promptText"] == "破壊対象を選択してください"


if __name__ == "__main__":
    test_select_destroy_choiceRequests_flow()
    test_multiple_pending_deferred_actions()
    test_level_point_selection()
    test_optional_ability_activation()
    print("All choiceRequests flow tests passed!")