# actions/process_damage.py
from helper import fetch_card_masters, resolve_targets, add_status, add_temp_status
import random

def handle_process_damage(card, act, item, owner_id):
    """
    サーバー側ダメージ処理
    1. デッキトップから指定枚数をダメージゾーンに移動
    2. TOカードの使用可否選択
    3. カラー付与（TO使用しない場合）
    4. 反射ダメージチェイン
    5. OnDamageトリガー
    """
    damage_value = int(act.get("value", 1))
    target_player_id = act.get("targetPlayerId")
    
    if not target_player_id:
        # デフォルトで敵プレイヤーを対象とする
        target_player_id = next((p["id"] for p in item["players"] if p["id"] != owner_id), None)
    
    if not target_player_id:
        return []
    
    events = []
    
    # プレイヤー情報を取得
    target_player = next((p for p in item["players"] if p["id"] == target_player_id), None)
    if not target_player:
        return []
    
    # デッキから指定枚数のカードを取得
    deck_cards = [c for c in item["cards"] if c["zone"] == "Deck" and c["ownerId"] == target_player_id]
    if len(deck_cards) < damage_value:
        damage_value = len(deck_cards)  # デッキが足りない場合は可能な限り
    
    # デッキトップから指定枚数を取得（シャッフル済みと仮定）
    damage_cards = deck_cards[:damage_value]
    
    # カードマスターデータを取得
    card_ids = [c["cardId"] for c in damage_cards]
    card_masters = fetch_card_masters(card_ids)
    
    # 1. ダメージゾーンに移動
    for damage_card in damage_cards:
        damage_card["zone"] = "DamageZone"
        events.append({
            "type": "MoveZone",
            "payload": {
                "cardId": damage_card["id"],
                "fromZone": "Deck",
                "toZone": "DamageZone"
            }
        })
    
    # 2. TOカードの処理
    for damage_card in damage_cards:
        card_master = card_masters.get(damage_card["cardId"], {})
        is_to = card_master.get("isTO", False)
        
        if is_to:
            # TOカードの使用可否選択
            selection_key = f"to_select_{damage_card['id']}"
            
            # 選択肢を提供
            events.append({
                "type": "SelectOption",
                "payload": {
                    "selectionKey": selection_key,
                    "options": ["use", "not_use"],
                    "prompt": f"TOカード {card_master.get('name', '不明')} を使用しますか？",
                    "cardId": damage_card["id"]
                }
            })
            
            # choiceRequestsに追加（クライアントが選択するまで待機）
            item.setdefault("choiceRequests", []).append({
                "requestId": selection_key,
                "playerId": target_player_id,
                "cardId": damage_card["id"],
                "type": "to_selection"
            })
            
        else:
            # 通常カードの場合はカラー付与
            available_colors = card_master.get("availableColors", ["Red", "Blue", "Green", "Yellow", "Purple"])
            assigned_color = random.choice(available_colors)
            
            damage_card["assignedColor"] = assigned_color
            events.append({
                "type": "AssignColor",
                "payload": {
                    "cardId": damage_card["id"],
                    "color": assigned_color
                }
            })
    
    # 3. 反射ダメージチェック
    reflection_events = check_reflection_damage(owner_id, target_player_id, damage_value, item)
    events.extend(reflection_events)
    
    # 4. OnDamageトリガー
    events.append({
        "type": "AbilityActivated",
        "payload": {
            "trigger": "OnDamage",
            "targetPlayerId": target_player_id,
            "damageValue": damage_value,
            "cardCount": len(damage_cards)
        }
    })
    
    return events

def check_reflection_damage(attacker_id, defender_id, damage_value, item):
    """
    反射ダメージのチェック
    """
    events = []
    
    # 防御側のフィールドカードでIsChainPainReflectステータスを持つカードを検索
    field_cards = [c for c in item["cards"] if c["zone"] == "Field" and c["ownerId"] == defender_id]
    
    for field_card in field_cards:
        has_reflect = any(
            status.get("key") == "IsChainPainReflect" 
            for status in field_card.get("statuses", [])
        )
        
        if has_reflect:
            # 反射ダメージを攻撃者に与える
            events.append({
                "type": "ReflectionDamage",
                "payload": {
                    "sourceCardId": field_card["id"],
                    "attackerId": attacker_id,
                    "defenderId": defender_id,
                    "originalDamage": damage_value
                }
            })
            
            # 攻撃者に対して追加のProcessDamageを発火
            events.append({
                "type": "ProcessDamage",
                "payload": {
                    "value": damage_value,
                    "targetPlayerId": attacker_id,
                    "isReflection": True
                }
            })
            
            break  # 1回だけ反射
    
    return events

def process_to_selection_result(damage_card, selected_value, item):
    """
    TO選択結果の処理
    """
    events = []
    
    if selected_value == "use":
        # TO効果を発動
        card_master = fetch_card_masters([damage_card["cardId"]])[damage_card["cardId"]]
        to_effect = card_master.get("toEffect", {})
        
        events.append({
            "type": "AbilityActivated",
            "payload": {
                "cardId": damage_card["id"],
                "ability": "TO",
                "effect": to_effect
            }
        })
        
    else:
        # TO使用しない場合はカラー付与
        card_master = fetch_card_masters([damage_card["cardId"]])[damage_card["cardId"]]
        available_colors = card_master.get("availableColors", ["Red", "Blue", "Green", "Yellow", "Purple"])
        assigned_color = random.choice(available_colors)
        
        damage_card["assignedColor"] = assigned_color
        events.append({
            "type": "AssignColor",
            "payload": {
                "cardId": damage_card["id"],
                "color": assigned_color
            }
        })
    
    # 選択結果を通知
    events.append({
        "type": "SelectOptionResult",
        "payload": {
            "cardId": damage_card["id"],
            "selectedValue": selected_value,
            "result": "processed"
        }
    })
    
    return events