# λ_code/actions/__init__.py
from importlib import import_module
import json, logging

# ここに追加したファイル名を列挙
_modules = [
    "battle_buff",
    "select",
    "select_option", 
    "destroy",
    "summon",
    "pay_cost",
    "gain_level",
    "destroy_level",
    "assign_color",
    "activate_cost",
    "player_status",
    "set_player_status",
    "transform",
    "counter_change",
    "apply_damage",
    "create_token",
    "call_method",
    "next_summon_buff",
    "cost_modifier",
    "set_status"
]

for name in _modules:
    import_module(f"actions.{name}")    # import 時にデコレータが走る