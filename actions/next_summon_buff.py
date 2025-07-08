# actions/next_summon_buff.py

def handle_next_summon_buff(card, act, item, owner_id):
    """
    次に召喚するカードに一時的効果を付与
    """
    keyword = act.get("keyword", "Power")
    value = int(act.get("value", 0))
    duration = int(act.get("duration", 1))
    
    # プレイヤー情報を取得
    player = next((p for p in item["players"] if p["id"] == owner_id), None)
    if not player:
        return []
    
    # 次召喚バフを設定
    next_summon_buffs = player.setdefault("nextSummonBuffs", [])
    next_summon_buffs.append({
        "keyword": keyword,
        "value": value,
        "duration": duration
    })
    
    return [{
        "type": "NextSummonBuff",
        "payload": {
            "playerId": owner_id,
            "keyword": keyword,
            "value": value,
            "duration": duration
        }
    }]