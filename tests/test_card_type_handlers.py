# tests/test_card_type_handlers.py
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lambda_function import (
    handle_monster_summon,
    handle_persistent_spell,
    handle_normal_spell,
    handle_field_card,
    notify_summon_card
)


class TestCardTypeHandlers:
    """Test the card type specific handlers"""
    
    def test_handle_monster_summon(self):
        """Test monster summon handler"""
        card = {"id": "monster1", "ownerId": "player1"}
        item = {"cards": [card]}
        
        events = handle_monster_summon(card, item)
        
        assert len(events) == 2
        assert events[0]["type"] == "OnSummon"
        assert events[0]["payload"]["cardId"] == "monster1"
        assert events[1]["type"] == "OnEnterField"
        assert events[1]["payload"]["cardId"] == "monster1"

    def test_handle_persistent_spell(self):
        """Test persistent spell handler"""
        card = {"id": "spell1", "ownerId": "player1"}
        item = {"cards": [card]}
        
        events = handle_persistent_spell(card, item)
        
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[0]["payload"]["cardId"] == "spell1"
        assert events[1]["type"] == "RegisterFieldEffect"
        assert events[1]["payload"]["cardId"] == "spell1"
        assert events[1]["payload"]["effectType"] == "PersistentSpell"

    def test_handle_normal_spell(self):
        """Test normal spell handler"""
        card = {"id": "spell2", "ownerId": "player1", "zone": "Hand"}
        item = {"cards": [card]}
        
        events = handle_normal_spell(card, item)
        
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[0]["payload"]["cardId"] == "spell2"
        assert events[1]["type"] == "MoveZone"
        assert events[1]["payload"]["cardId"] == "spell2"
        assert events[1]["payload"]["fromZone"] == "Hand"
        assert events[1]["payload"]["toZone"] == "Graveyard"
        # Check that the card zone was updated
        assert card["zone"] == "Graveyard"

    def test_handle_field_card(self):
        """Test field card handler"""
        card = {"id": "field1", "ownerId": "player1", "zone": "Hand"}
        item = {"cards": [card]}
        
        events = handle_field_card(card, item)
        
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[0]["payload"]["cardId"] == "field1"
        assert events[1]["type"] == "MoveZone"
        assert events[1]["payload"]["cardId"] == "field1"
        assert events[1]["payload"]["fromZone"] == "Hand"
        assert events[1]["payload"]["toZone"] == "Environment"
        # Check that the card zone was updated
        assert card["zone"] == "Environment"


class TestNotifySummonCard:
    """Test the main notify_summon_card function"""
    
    @patch('lambda_function.fetch_card_masters')
    @patch('lambda_function.detach_auras')
    def test_notify_summon_card_monster(self, mock_detach_auras, mock_fetch_masters):
        """Test notify_summon_card with monster type"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Monster"}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Verify master data was fetched
        mock_fetch_masters.assert_called_once_with(["base1"])
        
        # Verify auras were detached and zone was updated
        mock_detach_auras.assert_called_once_with(card, [card])
        assert card["zone"] == "Field"
        
        # Verify events
        assert len(events) == 2
        assert events[0]["type"] == "OnSummon"
        assert events[1]["type"] == "OnEnterField"

    @patch('lambda_function.fetch_card_masters')
    @patch('lambda_function.detach_auras')
    def test_notify_summon_card_persistent_spell(self, mock_detach_auras, mock_fetch_masters):
        """Test notify_summon_card with persistent spell type"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Spell", "isPersistentSpell": True}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1", 
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Verify auras were detached and zone was updated
        mock_detach_auras.assert_called_once_with(card, [card])
        assert card["zone"] == "Field"
        
        # Verify events
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[1]["type"] == "RegisterFieldEffect"

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_normal_spell(self, mock_fetch_masters):
        """Test notify_summon_card with normal spell type"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Spell", "isPersistentSpell": False}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1", 
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Verify zone was updated to Graveyard
        assert card["zone"] == "Graveyard"
        
        # Verify events
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[1]["type"] == "MoveZone"
        assert events[1]["payload"]["toZone"] == "Graveyard"

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_field_card(self, mock_fetch_masters):
        """Test notify_summon_card with field card type"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Field"}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Verify zone was updated to Environment
        assert card["zone"] == "Environment"
        
        # Verify events
        assert len(events) == 2
        assert events[0]["type"] == "OnPlay"
        assert events[1]["type"] == "MoveZone"
        assert events[1]["payload"]["toZone"] == "Environment"

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_equip_card(self, mock_fetch_masters):
        """Test notify_summon_card with equip card type (not implemented)"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Equip"}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Should return empty events for unimplemented type
        assert len(events) == 0

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_unknown_type(self, mock_fetch_masters):
        """Test notify_summon_card with unknown card type"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {"cardType": "Unknown"}
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Should return empty events for unknown type
        assert len(events) == 0

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_no_card_type(self, mock_fetch_masters):
        """Test notify_summon_card with no card type (defaults to Monster)"""
        # Setup mock data
        mock_fetch_masters.return_value = {
            "base1": {}  # No cardType field
        }
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Should default to Monster handling
        assert len(events) == 2
        assert events[0]["type"] == "OnSummon"
        assert events[1]["type"] == "OnEnterField"

    def test_notify_summon_card_card_not_found(self):
        """Test notify_summon_card when card is not found"""
        item = {"cards": []}
        
        events = notify_summon_card(item, "nonexistent", "player1")
        
        # Should return empty events
        assert len(events) == 0

    def test_notify_summon_card_no_base_card_id(self):
        """Test notify_summon_card when card has no baseCardId"""
        card = {
            "id": "card1",
            "ownerId": "player1",
            "zone": "Hand"
            # No baseCardId
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Should return empty events
        assert len(events) == 0

    @patch('lambda_function.fetch_card_masters')
    def test_notify_summon_card_no_master_data(self, mock_fetch_masters):
        """Test notify_summon_card when master data is not found"""
        # Setup mock data
        mock_fetch_masters.return_value = {}  # No master data
        
        card = {
            "id": "card1",
            "ownerId": "player1",
            "baseCardId": "base1",
            "zone": "Hand"
        }
        item = {"cards": [card]}
        
        events = notify_summon_card(item, "card1", "player1")
        
        # Should return empty events
        assert len(events) == 0


if __name__ == "__main__":
    pytest.main([__file__])