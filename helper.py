# helper.py
from decimal import Decimal
import json
import re
import os
import boto3
from typing import List, Dict, Any

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        return int(obj) if isinstance(obj, Decimal) else super().default(obj)

# DynamoDB client for card master fetching
dynamodb = boto3.client("dynamodb")

# ──────────────────────────────────────────────
# カードマスター取得
# ──────────────────────────────────────────────
def fetch_card_masters(card_ids: List[str]) -> Dict[str, Dict]:
    """
    CARD_MASTER_TABLE からまとめて取得 → { cardId: masterDict }
    """
    if not card_ids:
        return {}

    keys = [{"cardId": {"S": cid}} for cid in set(card_ids)]
    resp = dynamodb.batch_get_item(
        RequestItems={
            os.environ["CARD_MASTER_TABLE"]: {"Keys": keys}
        }
    )
    items = resp["Responses"].get(os.environ["CARD_MASTER_TABLE"], [])
    
    # DynamoDB形式のレスポンスを通常の辞書形式に変換
    result = {}
    for item in items:
        card_id = item["cardId"]["S"]
        # DynamoDB形式のアイテムをパースして通常の辞書形式に変換
        parsed_item = _parse_dynamodb_item(item)
        result[card_id] = parsed_item
    
    return result

def _parse_dynamodb_item(item: Dict) -> Dict:
    """DynamoDB形式のアイテムを通常の辞書形式に変換"""
    result = {}
    for key, value in item.items():
        if isinstance(value, dict):
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                result[key] = Decimal(value["N"])
            elif "BOOL" in value:
                result[key] = value["BOOL"]
            elif "L" in value:
                result[key] = [_parse_dynamodb_value(v) for v in value["L"]]
            elif "M" in value:
                result[key] = _parse_dynamodb_item(value["M"])
            else:
                result[key] = value
        else:
            result[key] = value
    return result

def _parse_dynamodb_value(value: Dict) -> Any:
    """DynamoDB形式の値を通常の値に変換"""
    if "S" in value:
        return value["S"]
    elif "N" in value:
        return Decimal(value["N"])
    elif "BOOL" in value:
        return value["BOOL"]
    elif "L" in value:
        return [_parse_dynamodb_value(v) for v in value["L"]]
    elif "M" in value:
        return _parse_dynamodb_item(value["M"])
    else:
        return value

# ---------------- Dynamo / Decimal -----------------
def d(val):
    """任意値→Decimal。-1, 0, int, str いずれでも OK"""
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        raise ValueError(f"cannot cast {val!r} to Decimal")

# ---------------- status helpers -------------------
def add_status(card, key, value):
    sts = card.setdefault("statuses", [])
    ex = next((s for s in sts if s["key"] == key), None)
    (ex.__setitem__("value", value) if ex else
     sts.append({"key": key, "value": value}))

def add_temp_status(card, key, value, expire_turn, *, source_id=None):
    tmp = card.setdefault("tempStatuses", [])
    tmp.append({
        "key": key,
        "value": str(value),
        "expireTurn": d(expire_turn),     # -1 = 永続
        "sourceId": source_id or card["id"]
    })

def keyword_map(k: str) -> str:
    return {
        "Power":   "TempPowerBoost",
        "Damage":  "TempDamageBoost",
        "Gail":    "TempGail",
        "Protect": "TempProtect",
    }.get(k, k)


# ---------------- target resolution constants ----------------
TARGET_ZONES = [
    "Field",
    "Environment", 
    "Counter",
    "Hand",
    "Deck",
    "Graveyard",
    "Exile",
    "DamageZone"
]

# ---------------- weighted random selection ----------------
import random

def weighted_random_select(options: List[str], weights: List[int]) -> str:
    """
    重み付きランダム選択を実行
    
    Args:
        options: 選択肢のリスト
        weights: 各選択肢の重み（整数）
    
    Returns:
        選択された選択肢
    """
    if not options or not weights or len(options) != len(weights):
        return ""
    
    # 重みの合計を計算
    total_weight = sum(weights)
    if total_weight <= 0:
        return ""
    
    # 0から合計重みの間でランダム値を生成
    rand_val = random.randint(1, total_weight)
    
    # 重みに基づいて選択肢を決定
    current_weight = 0
    for i, weight in enumerate(weights):
        current_weight += weight
        if rand_val <= current_weight:
            return options[i]
    
    # フォールバック（通常ここには来ない）
    return options[0] if options else ""

# ---------------- choice response cleanup ----------------
def cleanup_used_choice_response(item: Dict[str, Any], request_id: str) -> None:
    """
    使用済みのchoiceResponseを削除してメモリリークや二重適用を防ぐ
    """
    if "choiceResponses" in item:
        item["choiceResponses"] = [
            r for r in item["choiceResponses"] 
            if r.get("requestId") != request_id
        ]

# ---------------- target resolution ----------------
def resolve_targets(src: Dict[str, Any], action: Dict[str, Any], item: Dict[str, Any]) -> List[Dict]:
    print(f"resolve_targets: {src=}, {action=}, {item=}")
    # 1) selectionKey 優先
    sel_key = action.get("selectionKey") or action.get("sourceKey")
    if sel_key:
        # choiceResponses から値を取り出す
        responses = item.get("choiceResponses", [])
        # 例: {'requestId': sel_key, 'selectedIds': ['c1','c2',...]}
        resp = next((r for r in responses if r.get("requestId") == sel_key), None)
        if resp:
            # selectedIds があればそちらを優先、なければ selectedValue を１件として扱う
            ids = resp.get("selectedIds",
                          [resp["selectedValue"]] if resp.get("selectedValue") else [])
            if ids:
                targets = [c for c in item["cards"] if c["id"] in ids]
                cleanup_used_choice_response(item, sel_key)
                return targets

    if action["type"] == "Draw":
        return [src]

    # 2) 自動ターゲット取得
    pool = get_target_cards(src, action, item)

    # 3) フィルター適用
    flt = action.get("targetFilter", "")
    if flt:
        pool = apply_filter(pool, flt, item)

    # 4) 再利用用に保存
    if action.get("sourceKey"):
        item.setdefault("selections", {})[action["sourceKey"]] = [c["id"] for c in pool]

    return pool

def get_target_cards(src: Dict, action: Dict, item: Dict) -> List[Dict]:
    owner = src["ownerId"]
    target = action.get("target")
    cards = item["cards"]
    if target == "Self":
        return [src]
    if target == "PlayerField":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Field"]
    if target == "EnemyField":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Field"]
    if target == "AllField":
        return [c for c in cards if c["zone"] == "Field"]
    if target == "PlayerHand":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Hand"]
    if target == "EnemyHand":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Hand"]
    if target == "EitherHand":
        # 例: selections に前段で選択肢を入れていると仮定
        selected_owner = item.get("variables", {}).get("selectedOwner")
        oid = owner if selected_owner == "Player" else next(p["id"] for p in item["players"] if p["id"] != owner)
        return [c for c in cards if c["ownerId"] == oid and c["zone"] == "Hand"]
    if target == "PlayerDeckTop":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Deck"][: int(action.get("value", 1))]
    # パッシブアビリティ対象拡張: Environment ゾーン
    if target == "Environment":
        return [c for c in cards if c["zone"] == "Environment"]
    if target == "PlayerEnvironment":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Environment"]
    if target == "EnemyEnvironment":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Environment"]
    # パッシブアビリティ対象拡張: Counter ゾーン
    if target == "Counter":
        return [c for c in cards if c["zone"] == "Counter"]
    if target == "PlayerCounter":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Counter"]
    if target == "EnemyCounter":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Counter"]
    # パッシブアビリティ対象拡張: その他のゾーン
    if target == "PlayerGraveyard":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Graveyard"]
    if target == "EnemyGraveyard":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Graveyard"]
    if target == "AllGraveyard":
        return [c for c in cards if c["zone"] == "Graveyard"]
    if target == "PlayerExileZone":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Exile"]
    if target == "EnemyExileZone":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Exile"]
    if target == "AllExileZone":
        return [c for c in cards if c["zone"] == "Exile"]
    if target == "PlayerDamageZone":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "DamageZone"]
    if target == "EnemyDamageZone":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "DamageZone"]
    if target == "AllDamageZone":
        return [c for c in cards if c["zone"] == "DamageZone"]

    return []

def apply_filter(pool: List[Dict], flt: str, item: Dict) -> List[Dict]:
    # シンプルな key=value や key<=value パターンをサポート
    m = re.match(r"(\w+)(<=|>=|=)(.+)", flt)
    if not m:
        return pool
    key, op, rhs = m.groups()
    # カードのプロパティを取得するユーティリティ
    def get_prop(c: Dict, k: str):
        # 例: 'power' → c.get('currentPower')
        return {
            "power": c.get("currentPower", 0),
            "cost": int(c.get("baseData", {}).get("level", 0)),
            "color": c.get("baseData", {}).get("colorCosts", []),
        }.get(k, None)

    out = []
    for c in pool:
        val = get_prop(c, key)
        if val is None:
            continue
        # 数値比較
        if op in ("<=", ">=") and isinstance(val, (int, float)):
            if (op == "<=" and val <= int(rhs)) or (op == ">=" and val >= int(rhs)):
                out.append(c)
        # 完全一致（文字列 or list 含む）
        elif op == "=":
            # list の場合は包含チェック
            if isinstance(val, list) and rhs in val:
                out.append(c)
            elif str(val) == rhs:
                out.append(c)
    return out