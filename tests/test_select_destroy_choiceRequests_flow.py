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


if __name__ == "__main__":
    test_select_destroy_choiceRequests_flow()
    test_multiple_pending_deferred_actions()
    print("All choiceRequests flow tests passed!")