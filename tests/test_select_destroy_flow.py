# test_select_destroy_flow.py
import pytest
from unittest.mock import patch

# Test Select→Destroy flow
def test_select_destroy_flow():
    """
    Select→Destroyフローをテスト
    1. Selectアクションがカード選択肢を提示
    2. choiceResponsesに選択結果が保存される
    3. Destroyアクションが選択されたカードを破壊する
    """
    # Import after setting up the path
    from actions.select import handle_select
    from actions.destroy import handle_destroy
    
    # テストデータセットアップ
    test_card = {
        "id": "source-card",
        "ownerId": "player1",
        "zone": "Field"
    }
    
    test_item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field"},
            {"id": "card2", "ownerId": "player1", "zone": "Field"},
            {"id": "card3", "ownerId": "player2", "zone": "Field"}
        ],
        "choiceResponses": []
    }
    
    # Step 1: Select アクションを実行
    select_action = {
        "type": "Select",
        "target": "PlayerField",
        "selectionKey": "destroyTarget",
        "mode": "single",
        "prompt": "破壊対象のカードを選択してください"
    }
    
    select_events = handle_select(test_card, select_action, test_item, "player1")
    
    # SendChoiceRequest イベントが生成されることを確認
    assert len(select_events) == 1
    assert select_events[0]["type"] == "SendChoiceRequest"
    assert select_events[0]["payload"]["requestId"] == "destroyTarget"
    assert select_events[0]["payload"]["playerId"] == "player1"
    assert len(select_events[0]["payload"]["options"]) == 2  # player1の2枚のカード
    assert "card1" in select_events[0]["payload"]["options"]
    assert "card2" in select_events[0]["payload"]["options"]
    assert "card3" not in select_events[0]["payload"]["options"]  # 敵のカードは含まれない
    
    # Step 2: クライアントからのchoiceResponseをシミュレート
    test_item["choiceResponses"] = [
        {
            "requestId": "destroyTarget",
            "selectedIds": ["card1"]
        }
    ]
    
    # Step 3: Destroy アクションを実行
    destroy_action = {
        "type": "Destroy",
        "selectionKey": "destroyTarget"
    }
    
    destroy_events = handle_destroy(test_card, destroy_action, test_item, "player1")
    
    # 破壊イベントが生成されることを確認
    assert len(destroy_events) == 1
    assert destroy_events[0]["type"] == "Destroy"
    assert destroy_events[0]["payload"]["cardId"] == "card1"
    assert destroy_events[0]["payload"]["fromZone"] == "Field"
    assert destroy_events[0]["payload"]["toZone"] == "Graveyard"
    
    # カードが墓地に移動したことを確認
    card1 = next(c for c in test_item["cards"] if c["id"] == "card1")
    assert card1["zone"] == "Graveyard"
    
    # 使用済みのchoiceResponseがクリアされたことを確認
    assert len(test_item["choiceResponses"]) == 0


def test_select_no_targets():
    """
    選択対象がない場合のテスト
    """
    from actions.select import handle_select
    
    test_card = {
        "id": "source-card",
        "ownerId": "player1",
        "zone": "Field"
    }
    
    test_item = {
        "cards": [
            {"id": "card1", "ownerId": "player2", "zone": "Field"}  # 敵のカードのみ
        ],
        "choiceResponses": []
    }
    
    select_action = {
        "type": "Select",
        "target": "PlayerField",  # 自分のフィールドを対象
        "selectionKey": "target",
        "mode": "single"
    }
    
    events = handle_select(test_card, select_action, test_item, "player1")
    
    # 空の選択イベントが返されることを確認
    assert len(events) == 1
    assert events[0]["type"] == "Select"
    assert events[0]["payload"]["selectedIds"] == []
    assert "選択するカードがありません" in events[0]["payload"]["prompt"]


def test_select_multiple_mode():
    """
    複数選択モードのテスト
    """
    from actions.select import handle_select
    
    test_card = {
        "id": "source-card",
        "ownerId": "player1",
        "zone": "Field"
    }
    
    test_item = {
        "cards": [
            {"id": "card1", "ownerId": "player1", "zone": "Field"},
            {"id": "card2", "ownerId": "player1", "zone": "Field"},
            {"id": "card3", "ownerId": "player1", "zone": "Field"}
        ],
        "choiceResponses": []
    }
    
    select_action = {
        "type": "Select",
        "target": "PlayerField",
        "selectionKey": "multiTarget",
        "mode": "multiple",
        "value": 2  # 最大2枚
    }
    
    events = handle_select(test_card, select_action, test_item, "player1")
    
    assert len(events) == 1
    assert events[0]["type"] == "SendChoiceRequest"
    assert events[0]["payload"]["maxSelect"] == 2
    assert events[0]["payload"]["mode"] == "multiple"
    assert len(events[0]["payload"]["options"]) == 3


if __name__ == "__main__":
    test_select_destroy_flow()
    test_select_no_targets()
    test_select_multiple_mode()
    print("All tests passed!")