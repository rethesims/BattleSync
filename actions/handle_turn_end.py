# actions/handle_turn_end.py
import logging
from typing import List, Dict, Any

logger = logging.getLogger()

def handle_turn_end(card, act, item, owner_id):
    """
    OnTurnEnd トリガーの処理。
    ターン終了時の効果を実行する。
    
    Args:
        card: 効果を発動するカード
        act: アクション定義
        item: マッチ状態
        owner_id: 効果を発動するプレイヤーID
    
    Returns:
        List[Dict]: 発生したイベントのリスト
    """
    logger.info(f"handle_turn_end: card={card['id']} owner={owner_id}")
    
    events = []
    
    # OnTurnEnd トリガーの基本的な処理
    # 必要に応じて、永続効果の解除、カウンター増減、
    # 一時ステータスの処理などを実装
    
    # 例: 一時ステータスの解除（expireTurn が現在のターン以下のもの）
    turn_count = item.get("turnCount", 0)
    
    # フィールド上のカードから期限切れの一時ステータスを削除
    for c in item.get("cards", []):
        if c["zone"] == "Field":
            original_temp_count = len(c.get("tempStatuses", []))
            c["tempStatuses"] = [
                s for s in c.get("tempStatuses", []) 
                if s.get("expireTurn", -1) == -1 or s.get("expireTurn", -1) > turn_count
            ]
            
            # 削除された一時ステータスがあればイベントを発生
            removed_count = original_temp_count - len(c.get("tempStatuses", []))
            if removed_count > 0:
                events.append({
                    "type": "TempStatusExpired",
                    "payload": {
                        "cardId": c["id"],
                        "expiredCount": removed_count,
                        "turnCount": turn_count
                    }
                })
    
    # ターン終了時の効果実行完了イベント
    events.append({
        "type": "TurnEndProcessed",
        "payload": {
            "sourceCardId": card["id"],
            "turnCount": turn_count,
            "playerId": owner_id
        }
    })
    
    logger.info(f"handle_turn_end completed: {len(events)} events generated")
    return events