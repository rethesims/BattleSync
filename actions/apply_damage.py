# actions/apply_damage.py
from helper import resolve_targets

def handle_apply_damage(card, act, item, owner_id):
    """
    指定プレイヤーまたはカードにダメージを与える
    """
    damage_value = int(act.get("value", 1))
    target_type = act.get("target", "EnemyLeader")
    events = []
    
    # プレイヤーへのダメージ
    if target_type in ["PlayerLeader", "EnemyLeader"]:
        if target_type == "PlayerLeader":
            target_player_id = owner_id
        else:
            target_player_id = next((p["id"] for p in item["players"] if p["id"] != owner_id), None)
        
        if not target_player_id:
            return []
        
        # プレイヤー情報を取得
        player = next((p for p in item["players"] if p["id"] == target_player_id), None)
        if not player:
            return []
        
        # ダメージを適用
        current_hp = player.get("hp", 20)  # デフォルト HP
        new_hp = max(0, current_hp - damage_value)
        player["hp"] = new_hp
        
        events.append({
            "type": "ApplyDamage",
            "payload": {
                "targetType": "Player",
                "playerId": target_player_id,
                "damageValue": damage_value,
                "newHp": new_hp
            }
        })
    
    else:
        # カードへのダメージ
        targets = resolve_targets(card, act, item)
        
        for target in targets:
            # カードのダメージを増加
            current_damage = target.get("damage", 0)
            new_damage = current_damage + damage_value
            target["damage"] = new_damage
            
            events.append({
                "type": "ApplyDamage",
                "payload": {
                    "targetType": "Card",
                    "cardId": target["id"],
                    "damageValue": damage_value,
                    "newDamage": new_damage
                }
            })
    
    return events