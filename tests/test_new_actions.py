# tests/test_new_actions.py
import pytest
from unittest.mock import MagicMock
from actions.select import handle_select
from actions.destroy import handle_destroy
from actions.summon import handle_summon
from actions.pay_cost import handle_pay_cost
from actions.create_token import handle_create_token

class TestNewActions:
    def test_select_action(self):
        """Test Select action"""
        card = {"id": "card1", "ownerId": "player1"}
        act = {
            "type": "Select",
            "target": "PlayerField",
            "mode": "single",
            "selectionKey": "test_select"
        }
        item = {
            "cards": [
                {"id": "card2", "ownerId": "player1", "zone": "Field"},
                {"id": "card3", "ownerId": "player1", "zone": "Field"}
            ]
        }
        
        result = handle_select(card, act, item, "player1")
        
        assert len(result) == 1
        assert result[0]["type"] == "Select"
        assert result[0]["payload"]["selectionKey"] == "test_select"
        assert len(result[0]["payload"]["availableIds"]) == 2
        assert result[0]["payload"]["maxSelect"] == 1

    def test_destroy_action(self):
        """Test Destroy action"""
        card = {"id": "card1", "ownerId": "player1"}
        act = {
            "type": "Destroy",
            "target": "EnemyField"
        }
        item = {
            "cards": [
                {"id": "card2", "ownerId": "player2", "zone": "Field"},
                {"id": "card3", "ownerId": "player2", "zone": "Field"}
            ]
        }
        
        result = handle_destroy(card, act, item, "player1")
        
        assert len(result) == 2
        assert all(event["type"] == "Destroy" for event in result)
        assert all(event["payload"]["toZone"] == "Graveyard" for event in result)

    def test_summon_action(self):
        """Test Summon action"""
        card = {"id": "card1", "ownerId": "player1"}
        act = {
            "type": "Summon",
            "target": "PlayerHand"
        }
        item = {
            "cards": [
                {"id": "card2", "ownerId": "player1", "zone": "Hand"},
                {"id": "card3", "ownerId": "player1", "zone": "Hand"}
            ]
        }
        
        result = handle_summon(card, act, item, "player1")
        
        assert len(result) == 2
        assert all(event["type"] == "Summon" for event in result)
        assert all(event["payload"]["toZone"] == "Field" for event in result)

    def test_pay_cost_action(self):
        """Test PayCost action"""
        card = {"id": "card1", "ownerId": "player1"}
        act = {
            "type": "PayCost",
            "keyword": "LevelPoint",
            "value": 3
        }
        item = {
            "players": [
                {"id": "player1", "levelPoints": 5}
            ]
        }
        
        result = handle_pay_cost(card, act, item, "player1")
        
        assert len(result) == 1
        assert result[0]["type"] == "PayCost"
        assert result[0]["payload"]["costValue"] == 3
        assert result[0]["payload"]["remainingValue"] == 2

    def test_create_token_action(self):
        """Test CreateToken action"""
        card = {"id": "card1", "ownerId": "player1"}
        act = {
            "type": "CreateToken",
            "keyword": "SampleToken",
            "value": 2,
            "target": "Field"
        }
        item = {
            "cards": []
        }
        
        result = handle_create_token(card, act, item, "player1")
        
        assert len(result) == 2
        assert all(event["type"] == "CreateToken" for event in result)
        assert all(event["payload"]["baseCardId"] == "SampleToken" for event in result)
        assert len(item["cards"]) == 2  # トークンが追加されている

if __name__ == "__main__":
    pytest.main([__file__])