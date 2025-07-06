# λ_code/actions/battle_buff.py
import json
from action_registry import register
from helper import add_status, add_temp_status, keyword_map

@register("BattleBuff")
def handle(card, act, item, *_):
    # duration を数値化 (-1, 1, 2 …) ──────────────────────
    dur_raw = act.get("duration", 1)     # 無指定なら「1ターン」
    dur     = int(dur_raw)               # "-1" 文字列でも数値化できる

    keyword = act.get("keyword", "Power")
    value   = int(act.get("value", 0))
    k_mapped = keyword_map(keyword)

    # ── 恒常／一時の振り分け ─────────────────────────────
    if dur == -1:
        # 永続：statuses に直接入れる
        add_status(card, k_mapped, value)
    else:
        # 一時：tempStatuses（期限付き）
        expire_turn = item.get("turnCount", 0) + dur - 1
        # パッシブ効果の場合、sourceCardIdをアクションから取得
        source_id = act.get("sourceCardId")
        add_temp_status(card, k_mapped, value, expire_turn, source_id=source_id)

    # Power 以外のキーワードならフラグも立てる
    if keyword != "Power":
        add_status(card, f"Is{keyword}", True)

    # イベント生成
    return [{
        "type": "BattleBuff",
        "payload": {
            "cardId":   card["id"],
            "keyword":  keyword,
            "value":    value,
            "duration": dur          # -1 ならクライアントは恒常扱い
        }
    }]