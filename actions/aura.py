### actions/aura.py
from helper import resolve_targets, add_temp_status, keyword_map

def _apply_aura(card, act, item, owner_id, expire_turn=-1):
    """
    汎用 Aura ハンドラ
    act の `type` が PowerAura, DamageAura, KeywordAura のいずれか
    対象取得は resolve_targets に一任
    """
    events = []
    aura_type = act["type"]
    
    # PowerAura/DamageAura タイプに基づいて適切なキーワードを設定
    if aura_type == "PowerAura":
        keyword_key = keyword_map("Power")  # TempPowerBoost
        keyword = "Power"
    elif aura_type == "DamageAura":
        keyword_key = keyword_map("Damage")  # TempDamageBoost
        keyword = "Damage"
    else:
        keyword_key = keyword_map(act.get("keyword", "Power"))
        keyword = act.get("keyword", "Power")
    
    value = int(act.get("value", 0))
    for tgt in resolve_targets(card, act, item):
        add_temp_status(tgt, keyword_key, value, expire_turn, source_id=card["id"])
    events.append({
        "type": "AuraApplied",
        "payload": {
            "sourceCardId": card["id"],
            "auraType": aura_type,
            "keyword": keyword,
            "value": value,
        },
    })
    return events


def handle_power_aura(card, act, item, owner_id):
    return _apply_aura(card, act, item, owner_id)


def handle_damage_aura(card, act, item, owner_id):
    return _apply_aura(card, act, item, owner_id)


def handle_keyword_aura(card, act, item, owner_id):
    return _apply_aura(card, act, item, owner_id)