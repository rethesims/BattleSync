# actions/process_damage.py
from helper import resolve_targets, add_status, fetch_card_masters
import random

def handle_process_damage(card, act, item, owner_id):
    """
    サーバー側ダメージ処理
    
    処理フロー:
    1. デッキトップからN枚をダメージゾーンに移動
    2. 各カードについてTOチェック
    3. TO使用可否の選択処理
    4. カラー付与処理
    5. 反射ダメージチェイン処理
    6. OnDamageトリガー処理
    """
    damage_count = int(act.get("value", 1))
    target_player_id = act.get("targetPlayerId", owner_id)
    
    # 対象プレイヤーのデッキトップからカードを取得
    deck_cards = [c for c in item["cards"] 
                  if c["ownerId"] == target_player_id and c["zone"] == "Deck"]
    
    if not deck_cards:
        return []
    
    # デッキトップからダメージ分のカードを取得
    damage_cards = deck_cards[:damage_count]
    events = []
    
    # カードマスター情報を取得
    card_ids = [c["id"] for c in damage_cards]
    card_masters = fetch_card_masters(card_ids)
    
    # 1. デッキからダメージゾーンへカード移動
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
    
    # 2. 各ダメージカードのTO処理
    for damage_card in damage_cards:
        master_data = card_masters.get(damage_card["id"], {})
        is_to = master_data.get("isTO", False)
        
        if is_to:
            # TO使用可否の選択を追加
            selection_key = f"to_choice_{damage_card['id']}"
            
            # choiceRequests に追加
            item.setdefault("choiceRequests", []).append({
                "requestId": selection_key,
                "playerId": target_player_id,
                "promptText": f"TO {damage_card.get('name', 'カード')} を使用しますか？",
                "options": ["use", "not_use"],
                "selectionType": "option"
            })
            
            # 選択結果を確認
            responses = item.get("choiceResponses", [])
            response = next((r for r in responses if r.get("requestId") == selection_key), None)
            
            if response:
                selected_value = response.get("selectedValue", "not_use")
                
                if selected_value == "use":
                    # TO効果を発動
                    to_effect = master_data.get("toEffect", {})
                    if to_effect:
                        events.append({
                            "type": "AbilityActivated",
                            "payload": {
                                "sourceCardId": damage_card["id"],
                                "trigger": "ToEffect",
                                "effectData": to_effect
                            }
                        })
                        
                        # SelectOptionResult イベントを発行
                        events.append({
                            "type": "SelectOptionResult",
                            "payload": {
                                "selectionKey": selection_key,
                                "selectedValue": selected_value,
                                "playerId": target_player_id
                            }
                        })
                else:
                    # TO使用せず、カラーを付与
                    color = _assign_random_color(damage_card, master_data)
                    add_status(damage_card, f"ColorCost_{color}", 1)
                    
                    events.append({
                        "type": "AssignColor",
                        "payload": {
                            "cardId": damage_card["id"],
                            "color": color,
                            "value": 1,
                            "totalCost": 1
                        }
                    })
                    
                    # SelectOptionResult イベントを発行
                    events.append({
                        "type": "SelectOptionResult",
                        "payload": {
                            "selectionKey": selection_key,
                            "selectedValue": selected_value,
                            "playerId": target_player_id
                        }
                    })
                
                # 使用済みレスポンスを削除
                item["choiceResponses"] = [r for r in item["choiceResponses"] 
                                         if r.get("requestId") != selection_key]
            else:
                # まだ選択されていない場合、SelectOptionイベントを発行
                events.append({
                    "type": "SelectOption",
                    "payload": {
                        "selectionKey": selection_key,
                        "options": ["use", "not_use"],
                        "prompt": f"TO {damage_card.get('name', 'カード')} を使用しますか？",
                        "playerId": target_player_id
                    }
                })
        else:
            # TO以外のカードにはランダムカラーを付与
            color = _assign_random_color(damage_card, master_data)
            add_status(damage_card, f"ColorCost_{color}", 1)
            
            events.append({
                "type": "AssignColor",
                "payload": {
                    "cardId": damage_card["id"],
                    "color": color,
                    "value": 1,
                    "totalCost": 1
                }
            })
    
    # 3. 反射ダメージチェック
    reflection_events = _check_reflection_damage(card, target_player_id, damage_count, item)
    events.extend(reflection_events)
    
    # 4. OnDamageトリガー処理
    events.append({
        "type": "AbilityActivated",
        "payload": {
            "sourceCardId": card["id"],
            "trigger": "OnDamage",
            "targetPlayerId": target_player_id,
            "damageCount": damage_count
        }
    })
    
    return events

def _assign_random_color(card, master_data):
    """
    カードにランダムなカラーを付与
    """
    # マスターデータにカラー情報があればそれを使用
    available_colors = master_data.get("availableColors", ["Red", "Blue", "Green", "Yellow"])
    
    if isinstance(available_colors, list) and available_colors:
        return random.choice(available_colors)
    else:
        # デフォルトのカラー選択
        return random.choice(["Red", "Blue", "Green", "Yellow"])

def _check_reflection_damage(source_card, target_player_id, damage_count, item):
    """
    反射ダメージをチェックし、IsChainPainReflectステータスがある場合は反射ダメージを発生
    """
    events = []
    
    # 対象プレイヤーのカードでIsChainPainReflectステータスを持つものを探す
    target_cards = [c for c in item["cards"] 
                   if c["ownerId"] == target_player_id and c["zone"] == "Field"]
    
    for target_card in target_cards:
        statuses = target_card.get("statuses", [])
        temp_statuses = target_card.get("tempStatuses", [])
        
        # IsChainPainReflectステータスをチェック
        has_reflection = False
        for status in statuses + temp_statuses:
            if status.get("key") == "IsChainPainReflect":
                has_reflection = True
                break
        
        if has_reflection:
            # 反射ダメージを発生（元のカードのオーナーに対して）
            reflection_event = {
                "type": "ProcessDamage",
                "payload": {
                    "sourceCardId": target_card["id"],
                    "targetPlayerId": source_card["ownerId"],
                    "value": damage_count,
                    "isReflection": True
                }
            }
            events.append(reflection_event)
            
            # 反射ダメージイベントを発行
            events.append({
                "type": "ReflectionDamage",
                "payload": {
                    "sourceCardId": target_card["id"],
                    "targetPlayerId": source_card["ownerId"],
                    "damageCount": damage_count
                }
            })
    
    return events