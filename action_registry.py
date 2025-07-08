# 1) ここでまずレジストリ定義
_registry: dict[str, callable] = {}

def register(name: str):
    def _wrap(fn):
        _registry[name] = fn
        return fn
    return _wrap

def get(name: str):
    return _registry.get(name)

# 2) レジストリ定義後にアクションを import & 登録

from actions.draw       import handle_draw
from actions.move_zone  import handle_move_zone
from actions.aura       import handle_power_aura, handle_damage_aura, handle_keyword_aura
from actions.select     import handle_select
from actions.select_option import handle_select_option
from actions.destroy    import handle_destroy
from actions.summon     import handle_summon
from actions.pay_cost   import handle_pay_cost
from actions.gain_level import handle_gain_level
from actions.destroy_level import handle_destroy_level
from actions.assign_color import handle_assign_color
from actions.activate_cost import handle_activate_cost
from actions.player_status import handle_player_status
from actions.set_player_status import handle_set_player_status
from actions.transform  import handle_transform
from actions.counter_change import handle_counter_change
from actions.apply_damage import handle_apply_damage
from actions.create_token import handle_create_token
from actions.call_method import handle_call_method
from actions.next_summon_buff import handle_next_summon_buff
from actions.cost_modifier import handle_cost_modifier
from actions.set_status import handle_set_status

@register("Draw")
def _draw(card, act, item, owner_id):
    return handle_draw(card, act, item, owner_id)

@register("PowerAura")
def _pa(card, act, item, owner_id):
    return handle_power_aura(card, act, item, owner_id)

@register("DamageAura")
def _da(card, act, item, owner_id):
    return handle_damage_aura(card, act, item, owner_id)

@register("KeywordAura")
def _ka(card, act, item, owner_id):
    return handle_keyword_aura(card, act, item, owner_id)

@register("Select")
def _select(card, act, item, owner_id):
    return handle_select(card, act, item, owner_id)

@register("SelectOption")
def _select_option(card, act, item, owner_id):
    return handle_select_option(card, act, item, owner_id)

@register("Destroy")
def _destroy(card, act, item, owner_id):
    return handle_destroy(card, act, item, owner_id)

@register("Summon")
def _summon(card, act, item, owner_id):
    return handle_summon(card, act, item, owner_id)

@register("PayCost")
def _pay_cost(card, act, item, owner_id):
    return handle_pay_cost(card, act, item, owner_id)

@register("GainLevel")
def _gain_level(card, act, item, owner_id):
    return handle_gain_level(card, act, item, owner_id)

@register("DestroyLevel")
def _destroy_level(card, act, item, owner_id):
    return handle_destroy_level(card, act, item, owner_id)

@register("AssignColor")
def _assign_color(card, act, item, owner_id):
    return handle_assign_color(card, act, item, owner_id)

@register("ActivateCost")
def _activate_cost(card, act, item, owner_id):
    return handle_activate_cost(card, act, item, owner_id)

@register("PlayerStatus")
def _player_status(card, act, item, owner_id):
    return handle_player_status(card, act, item, owner_id)

@register("SetPlayerStatus")
def _set_player_status(card, act, item, owner_id):
    return handle_set_player_status(card, act, item, owner_id)

@register("Transform")
def _transform(card, act, item, owner_id):
    return handle_transform(card, act, item, owner_id)

@register("CounterChange")
def _counter_change(card, act, item, owner_id):
    return handle_counter_change(card, act, item, owner_id)

@register("ApplyDamage")
def _apply_damage(card, act, item, owner_id):
    return handle_apply_damage(card, act, item, owner_id)

@register("CreateToken")
def _create_token(card, act, item, owner_id):
    return handle_create_token(card, act, item, owner_id)

@register("CallMethod")
def _call_method(card, act, item, owner_id):
    return handle_call_method(card, act, item, owner_id)

@register("NextSummonBuff")
def _next_summon_buff(card, act, item, owner_id):
    return handle_next_summon_buff(card, act, item, owner_id)

@register("CostModifier")
def _cost_modifier(card, act, item, owner_id):
    return handle_cost_modifier(card, act, item, owner_id)

@register("SetStatus")
def _set_status(card, act, item, owner_id):
    return handle_set_status(card, act, item, owner_id)

# 汎用移動系アクションタイプ → 移動先ゾーン のマッピング
_zone_map = {
    "Bounce": "Hand",
    "Discard": "Graveyard",
    "Exile": "ExileZone",
    "MoveField": "Field",
    "MoveDeck": "Deck",
    "MoveToDamageZone": "DamageZone",
}

# マッピングをループして、各アクションをデコレータ登録
for action_type, zone in _zone_map.items():
    @register(action_type)
    def _move_handler(card, act, item, owner_id, zone=zone):
        # act に toZone を注入して汎用ハンドラを呼び出し
        act_with_zone = {**act, "toZone": zone}
        return handle_move_zone(card, act_with_zone, item, owner_id)
