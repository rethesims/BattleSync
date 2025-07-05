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
