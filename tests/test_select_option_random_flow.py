import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lambda_function import handle_trigger
from helper import d


class TestSelectOptionRandomFlow(unittest.TestCase):
    """SelectOption の mode="random" でのフロー統合テスト"""
    
    def setUp(self):
        """テスト用のデータを準備"""
        self.test_item = {
            "cards": [
                {
                    "id": "test_card_001",
                    "baseCardId": "test_01",
                    "ownerId": "p1",
                    "zone": "Field",
                    "power": d(2000),
                    "damage": d(1),
                    "level": d(5),
                    "effectList": []
                }
            ],
            "choiceResponses": [],
            "pendingDeferred": []
        }
        
        self.test_card = {
            "id": "test_card_001",
            "baseCardId": "test_01",
            "ownerId": "p1",
            "zone": "Field",
            "power": d(2000),
            "damage": d(1),
            "level": d(5),
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "SelectOption",
                            "mode": "random",
                            "options": ["token_001", "token_002", "token_003"],
                            "weights": [10, 40, 50],
                            "selectionKey": "RandomSelectKey",
                            "deferred": False
                        },
                        {
                            "type": "Transform",
                            "target": "Self",
                            "selectionKey": "RandomSelectKey", 
                            "deferred": False
                        }
                    ]
                }
            ]
        }
    
    @patch('helper.fetch_card_masters')
    def test_random_select_option_immediate_transform(self, mock_fetch_masters):
        """mode="random" の SelectOption で後続の Transform が即座に実行されることを確認"""
        
        # カードマスターデータのモック
        mock_fetch_masters.return_value = {
            "token_001": {"power": 1000, "damage": 0, "level": 3},
            "token_002": {"power": 1500, "damage": 1, "level": 4},
            "token_003": {"power": 2000, "damage": 2, "level": 5}
        }
        
        # handle_trigger を実行
        events = handle_trigger(self.test_card, "OnSummon", self.test_item)
        
        # 結果を検証
        # 1. SelectOption と Transform の両方のイベントが生成されている
        select_events = [e for e in events if e["type"] == "SelectOption"]
        transform_events = [e for e in events if e["type"] == "Transform"]
        
        self.assertEqual(len(select_events), 1, "SelectOption イベントが1つ生成されるべき")
        self.assertEqual(len(transform_events), 1, "Transform イベントが1つ生成されるべき")
        
        # 2. choiceResponses に選択結果が保存されている
        choice_responses = self.test_item.get("choiceResponses", [])
        self.assertEqual(len(choice_responses), 1, "choiceResponses に1つの選択結果が保存されるべき")
        
        choice_response = choice_responses[0]
        self.assertEqual(choice_response["requestId"], "RandomSelectKey")
        self.assertIn(choice_response["selectedValue"], ["token_001", "token_002", "token_003"])
        
        # 3. カードが実際に変身している
        transformed_card = self.test_item["cards"][0]
        self.assertIn(transformed_card["baseCardId"], ["token_001", "token_002", "token_003"])
        self.assertNotEqual(transformed_card["baseCardId"], "test_01", "カードが変身しているべき")
        
        # 4. pendingDeferred が空である（即座に実行されたため）
        self.assertEqual(len(self.test_item.get("pendingDeferred", [])), 0, "pendingDeferred は空であるべき")
        
        # 5. Transform イベントのペイロードが正しい
        transform_event = transform_events[0]
        self.assertEqual(transform_event["payload"]["cardId"], "test_card_001")
        self.assertEqual(transform_event["payload"]["fromCardId"], "test_01")
        self.assertIn(transform_event["payload"]["toCardId"], ["token_001", "token_002", "token_003"])
    
    def test_client_mode_select_option_deferred_transform(self):
        """mode="client" の SelectOption で後続の Transform が pendingDeferred に保存されることを確認"""
        
        # SelectOption の mode を "client" に変更
        self.test_card["effectList"][0]["actions"][0]["mode"] = "client"
        
        # handle_trigger を実行
        events = handle_trigger(self.test_card, "OnSummon", self.test_item)
        
        # 結果を検証
        # 1. SelectOption イベントのみ生成され、Transform は実行されない
        select_events = [e for e in events if e["type"] == "SelectOption"]
        transform_events = [e for e in events if e["type"] == "Transform"]
        
        self.assertEqual(len(select_events), 1, "SelectOption イベントが1つ生成されるべき")
        self.assertEqual(len(transform_events), 0, "Transform イベントは生成されないべき")
        
        # 2. choiceResponses は空である（クライアント選択待ち）
        choice_responses = self.test_item.get("choiceResponses", [])
        self.assertEqual(len(choice_responses), 0, "choiceResponses は空であるべき")
        
        # 3. カードは変身していない
        original_card = self.test_item["cards"][0]
        self.assertEqual(original_card["baseCardId"], "test_01", "カードは変身していないべき")
        
        # 4. pendingDeferred に Transform アクションが保存されている
        pending_deferred = self.test_item.get("pendingDeferred", [])
        self.assertEqual(len(pending_deferred), 1, "pendingDeferred に1つのアクションが保存されるべき")
        
        deferred_action = pending_deferred[0]
        self.assertEqual(deferred_action["type"], "Transform")
        self.assertEqual(deferred_action["selectionKey"], "RandomSelectKey")


if __name__ == "__main__":
    unittest.main()