import pytest
import json
from unittest.mock import Mock, patch
from moto import mock_dynamodb
import boto3
from decimal import Decimal

# テスト対象をインポート
from lambda_function import handle_trigger, resolve, apply_action

class TestDeferredFlow:
    """Deferred アクション機能のテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される共通セットアップ"""
        # テスト用のアイテムデータを準備
        self.item = {
            "cards": [
                {
                    "id": "card_001",
                    "ownerId": "player_1",
                    "zone": "Field",
                    "power": 1000,
                    "damage": 500,
                    "tempStatuses": [],
                    "statuses": [],
                    "effectList": []
                },
                {
                    "id": "card_002", 
                    "ownerId": "player_2",
                    "zone": "Field",
                    "power": 1500,
                    "damage": 750,
                    "tempStatuses": [],
                    "statuses": [],
                    "effectList": []
                }
            ],
            "players": [
                {"id": "player_1", "name": "Player1"},
                {"id": "player_2", "name": "Player2"}
            ],
            "turnPlayerId": "player_1",
            "choiceResponses": []
        }
    
    def test_handle_trigger_immediate_actions_only(self):
        """即座実行アクションのみの場合のテスト"""
        # テストカードに即座実行アクションのみを設定
        card = {
            "id": "test_card",
            "ownerId": "player_1",
            "zone": "Field",
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "Select",
                            "target": "EnemyField",
                            "selectionKey": "destroyTarget",
                            "mode": "single",
                            "deferred": False  # 即座実行
                        }
                    ]
                }
            ]
        }
        
        with patch('lambda_function.apply_action') as mock_apply:
            mock_apply.return_value = [{"type": "SendChoiceRequest", "payload": {}}]
            
            result = handle_trigger(card, "OnSummon", self.item)
            
            # 即座実行アクションが呼ばれることを確認
            mock_apply.assert_called_once()
            
            # OnChoiceCompleteイベントが生成されないことを確認
            choice_complete_events = [e for e in result if e["type"] == "OnChoiceComplete"]
            assert len(choice_complete_events) == 0
            
            # AbilityActivatedイベントが先頭に追加されることを確認
            assert result[0]["type"] == "AbilityActivated"
    
    def test_handle_trigger_deferred_actions_only(self):
        """遅延実行アクションのみの場合のテスト"""
        # テストカードに遅延実行アクションのみを設定
        card = {
            "id": "test_card",
            "ownerId": "player_1",
            "zone": "Field",
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "Destroy",
                            "selectionKey": "destroyTarget",
                            "deferred": True  # 遅延実行
                        }
                    ]
                }
            ]
        }
        
        with patch('lambda_function.apply_action') as mock_apply:
            result = handle_trigger(card, "OnSummon", self.item)
            
            # 即座実行アクションが呼ばれないことを確認
            mock_apply.assert_not_called()
            
            # OnChoiceCompleteイベントが生成されることを確認
            choice_complete_events = [e for e in result if e["type"] == "OnChoiceComplete"]
            assert len(choice_complete_events) == 1
            
            # OnChoiceCompleteイベントの内容を確認
            event = choice_complete_events[0]
            assert event["payload"]["sourceCardId"] == "test_card"
            assert event["payload"]["trigger"] == "OnSummon"
            assert len(event["payload"]["deferredActions"]) == 1
            assert event["payload"]["deferredActions"][0]["type"] == "Destroy"
    
    def test_handle_trigger_mixed_actions(self):
        """即座実行と遅延実行の混合アクションのテスト"""
        # テストカードに即座実行と遅延実行アクションを設定
        card = {
            "id": "test_card",
            "ownerId": "player_1",
            "zone": "Field",
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "Select",
                            "target": "EnemyField",
                            "selectionKey": "destroyTarget",
                            "mode": "single",
                            "deferred": False  # 即座実行
                        },
                        {
                            "type": "Destroy",
                            "selectionKey": "destroyTarget",
                            "deferred": True  # 遅延実行
                        }
                    ]
                }
            ]
        }
        
        with patch('lambda_function.apply_action') as mock_apply:
            mock_apply.return_value = [{"type": "SendChoiceRequest", "payload": {}}]
            
            result = handle_trigger(card, "OnSummon", self.item)
            
            # 即座実行アクションが呼ばれることを確認
            mock_apply.assert_called_once()
            
            # OnChoiceCompleteイベントが生成されることを確認
            choice_complete_events = [e for e in result if e["type"] == "OnChoiceComplete"]
            assert len(choice_complete_events) == 1
            
            # selectionKeyが正しく設定されることを確認
            event = choice_complete_events[0]
            assert event["payload"]["selectionKey"] == "destroyTarget"
    
    def test_resolve_onchoicecomplete_event(self):
        """OnChoiceCompleteイベントの処理テスト"""
        # choiceResponsesを設定
        self.item["choiceResponses"] = [
            {
                "requestId": "destroyTarget",
                "selectedIds": ["card_002"]
            }
        ]
        
        # OnChoiceCompleteイベントを準備
        initial_events = [
            {
                "type": "OnChoiceComplete",
                "payload": {
                    "selectionKey": "destroyTarget",
                    "sourceCardId": "card_001",
                    "trigger": "OnSummon",
                    "deferredActions": [
                        {
                            "type": "Destroy",
                            "selectionKey": "destroyTarget"
                        }
                    ]
                }
            }
        ]
        
        with patch('lambda_function.apply_action') as mock_apply:
            mock_apply.return_value = [{"type": "Destroy", "payload": {"cardIds": ["card_002"]}}]
            
            result = resolve(initial_events, self.item)
            
            # apply_actionが正しく呼ばれることを確認
            mock_apply.assert_called_once()
            
            # 正しいパラメータで呼ばれることを確認
            call_args = mock_apply.call_args
            assert call_args[0][0]["id"] == "card_001"  # source_card
            assert call_args[0][1]["type"] == "Destroy"  # action
            assert call_args[0][1]["selectionKey"] == "destroyTarget"  # selectionKey が設定されている
    
    def test_resolve_regular_trigger_event(self):
        """通常のトリガーイベントの処理テスト"""
        # 通常のトリガーイベントを準備
        initial_events = [
            {
                "type": "OnSummon",
                "payload": {
                    "cardId": "card_001"
                }
            }
        ]
        
        with patch('lambda_function.handle_trigger') as mock_handle:
            mock_handle.return_value = [{"type": "AbilityActivated", "payload": {}}]
            
            result = resolve(initial_events, self.item)
            
            # handle_triggerが正しく呼ばれることを確認
            mock_handle.assert_called_once()
            
            # 正しいパラメータで呼ばれることを確認
            call_args = mock_handle.call_args
            assert call_args[0][0]["id"] == "card_001"  # card
            assert call_args[0][1] == "OnSummon"  # trigger
    
    def test_deferred_action_selectionkey_inheritance(self):
        """deferredアクションのselectionKey継承テスト"""
        # selectionKeyを持たないdeferredアクションをテスト
        card = {
            "id": "test_card",
            "ownerId": "player_1",
            "zone": "Field",
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "Select",
                            "target": "EnemyField",
                            "selectionKey": "targetSelection",
                            "mode": "single",
                            "deferred": False
                        },
                        {
                            "type": "Destroy",
                            # selectionKeyなし - 自動で継承される
                            "deferred": True
                        }
                    ]
                }
            ]
        }
        
        with patch('lambda_function.apply_action') as mock_apply:
            mock_apply.return_value = [{"type": "SendChoiceRequest", "payload": {}}]
            
            result = handle_trigger(card, "OnSummon", self.item)
            
            # OnChoiceCompleteイベントを確認
            choice_complete_events = [e for e in result if e["type"] == "OnChoiceComplete"]
            assert len(choice_complete_events) == 1
            
            # selectionKeyが正しく設定されることを確認
            event = choice_complete_events[0]
            assert event["payload"]["selectionKey"] == "targetSelection"
    
    def test_resolve_with_recursive_events(self):
        """再帰的なイベント処理のテスト"""
        # OnChoiceCompleteイベントが新しいトリガーイベントを生成する場合
        initial_events = [
            {
                "type": "OnChoiceComplete",
                "payload": {
                    "selectionKey": "destroyTarget",
                    "sourceCardId": "card_001",
                    "trigger": "OnSummon",
                    "deferredActions": [
                        {
                            "type": "Destroy",
                            "selectionKey": "destroyTarget"
                        }
                    ]
                }
            }
        ]
        
        with patch('lambda_function.apply_action') as mock_apply:
            # apply_actionが新しいトリガーイベントを生成
            mock_apply.return_value = [
                {"type": "OnDestroy", "payload": {"cardId": "card_002"}}
            ]
            
            with patch('lambda_function.handle_trigger') as mock_handle:
                mock_handle.return_value = [{"type": "AbilityActivated", "payload": {}}]
                
                result = resolve(initial_events, self.item)
                
                # apply_actionとhandle_triggerが両方呼ばれることを確認
                mock_apply.assert_called_once()
                mock_handle.assert_called_once()
                
                # 結果に両方のイベントが含まれることを確認
                assert len(result) >= 2
    
    def test_no_deferred_actions_no_onchoicecomplete(self):
        """deferredアクションがない場合にOnChoiceCompleteが生成されないことを確認"""
        card = {
            "id": "test_card",
            "ownerId": "player_1",
            "zone": "Field",
            "effectList": [
                {
                    "trigger": "OnSummon",
                    "actions": [
                        {
                            "type": "PowerAura",
                            "target": "Self",
                            "value": 500
                            # deferredキーがない（デフォルトでfalse）
                        }
                    ]
                }
            ]
        }
        
        with patch('lambda_function.apply_action') as mock_apply:
            mock_apply.return_value = [{"type": "PowerAura", "payload": {}}]
            
            result = handle_trigger(card, "OnSummon", self.item)
            
            # OnChoiceCompleteイベントが生成されないことを確認
            choice_complete_events = [e for e in result if e["type"] == "OnChoiceComplete"]
            assert len(choice_complete_events) == 0
            
            # 通常のアクションが実行されることを確認
            mock_apply.assert_called_once()