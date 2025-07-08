# lambda_function.py
import os, json, boto3, logging
from datetime import datetime, timezone
from decimal import Decimal
from importlib import import_module

# --- 自前モジュール -----------------------------------------
from helper import (
    add_status, add_temp_status, keyword_map, d, resolve_targets,
    DecimalEncoder, TARGET_ZONES,
)
from action_registry import get as get_handler  # ここがディスパッチ
import actions  # noqa  (サイドエフェクトで handler 登録)

# --- AWS 初期化 ---------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["MATCH_TABLE"])
leader_table = ddb.Table(os.environ["LEADER_MASTER_TABLE"])
ai = boto3.client("lambda")
leader_cache: dict[str, dict] = {}
EVOLVE_THRESHOLDS = [4, 7]

# ---------------- Utility ------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def bump(item):
    item["matchVersion"] = item.get("matchVersion", Decimal(0)) + 1


def clear_expired(cards, turn_no):
    for c in cards:
        c["tempStatuses"] = [
            s for s in c.get("tempStatuses", []) if s["expireTurn"] == -1 or s["expireTurn"] > turn_no
        ]


def detach_auras(leaver, cards):
    for c in cards:
        c["tempStatuses"] = [
            s
            for s in c.get("tempStatuses", [])
            if not (s.get("sourceId") == leaver["id"] and s["expireTurn"] == -1)
        ]

# ---------- 超簡易ターゲットセレクター -----------------------

def select_targets(src, act, item):
    trg = act.get("target", "Self")
    cards = item["cards"]
    owner = src["ownerId"]
    if trg == "Self":
        return [src]
    if trg == "PlayerField":
        return [c for c in cards if c["ownerId"] == owner and c["zone"] == "Field"]
    if trg == "EnemyField":
        return [c for c in cards if c["ownerId"] != owner and c["zone"] == "Field"]
    if trg == "AllField":
        return [c for c in cards if c["zone"] == "Field"]
    return []

# ---------- Effect / Trigger 解決 ----------------------------

def _payload_to_dict(pld):
    """互換用：str なら json.loads、dict ならそのまま"""
    if isinstance(pld, str):
        return json.loads(pld)
    return pld


def handle_trigger(card, trig, item):
    res = []
    hit = False
    logger.info(f"handle_trigger: card={card['id']} trigger={trig}")
    for eff in card.get("effectList", []):
        if eff.get("trigger") != trig:
            continue
        logger.info(f"  matched effect: {eff}")
        hit = True
        for a in eff.get("actions", []):
            logger.info(f"    invoking action: {a}")
            res += apply_action(card, a, item, card["ownerId"])
    if hit:
        res.insert(0, {"type": "AbilityActivated", "payload": {"sourceCardId": card["id"], "trigger": trig}})
        logger.info(f"  inserted AbilityActivated for {card['id']}")
    return res


def resolve(initial, item):
    evs = list(initial)
    i = 0
    while i < len(evs):
        pld = _payload_to_dict(evs[i]["payload"])
        cid = pld.get("cardId")
        card = next((c for c in item["cards"] if c["id"] == cid), None)
        if card:
            evs += handle_trigger(card, evs[i]["type"], item)
        i += 1
    return evs

def apply_action(card, act, item, owner_id):
    handler = get_handler(act["type"])
    if not handler:
        logger.warning("Unhandled action type: %s", act["type"])
        return []
    
    logger.info(f"apply_action: card={card['id']} action={act['type']} owner={owner_id}")

    # ① 対象を解決する
    targets = resolve_targets(card, act, item)
    logger.info(f"  targets resolved: {[t['id'] for t in targets]}")
    events = []

    # ② 各対象に対してハンドラを実行
    for tgt in targets:
        events += handler(tgt, act, item, owner_id)

    return events

# ──────────────────────────────────────────────
# 条件式の評価
# ──────────────────────────────────────────────

def evaluate_condition(cond: str, card: dict, item: dict) -> bool:
    """
    条件式をパースして真偽を返す。
    拡張されたパッシブアビリティ対象用の条件評価機能。
    """
    if not cond:
        return True
    
    print(f"Evaluating condition: {cond} for card {card['id']}")
    
    # 自分ターンかつ自分フィールド枚数 == N
    if cond.startswith("PlayerTurnAndSelfFieldCount=="):
        try:
            n = int(cond.split("==",1)[1])
        except ValueError:
            print(f"  Invalid condition format: {cond}")
            return False
        return (item["turnPlayerId"] == card["ownerId"] and
                sum(1 for c in item["cards"]
                    if c["ownerId"] == card["ownerId"] and c["zone"] == "Field") == n)
    
    # 敵フィールド枚数の条件評価
    if cond.startswith("EnemyFieldCount"):
        try:
            if ">=" in cond:
                n = int(cond.split(">=",1)[1])
                enemy_field_count = sum(1 for c in item["cards"]
                                      if c["ownerId"] != card["ownerId"] and c["zone"] == "Field")
                return enemy_field_count >= n
            elif "==" in cond:
                n = int(cond.split("==",1)[1])
                enemy_field_count = sum(1 for c in item["cards"]
                                      if c["ownerId"] != card["ownerId"] and c["zone"] == "Field")
                return enemy_field_count == n
            elif "<=" in cond:
                n = int(cond.split("<=",1)[1])
                enemy_field_count = sum(1 for c in item["cards"]
                                      if c["ownerId"] != card["ownerId"] and c["zone"] == "Field")
                return enemy_field_count <= n
        except ValueError:
            print(f"  Invalid condition format: {cond}")
            return False
    
    # 自分フィールド枚数の条件評価
    if cond.startswith("PlayerFieldCount"):
        try:
            if ">=" in cond:
                n = int(cond.split(">=",1)[1])
                player_field_count = sum(1 for c in item["cards"]
                                       if c["ownerId"] == card["ownerId"] and c["zone"] == "Field")
                return player_field_count >= n
            elif "==" in cond:
                n = int(cond.split("==",1)[1])
                player_field_count = sum(1 for c in item["cards"]
                                       if c["ownerId"] == card["ownerId"] and c["zone"] == "Field")
                return player_field_count == n
            elif "<=" in cond:
                n = int(cond.split("<=",1)[1])
                player_field_count = sum(1 for c in item["cards"]
                                       if c["ownerId"] == card["ownerId"] and c["zone"] == "Field")
                return player_field_count <= n
        except ValueError:
            print(f"  Invalid condition format: {cond}")
            return False
    
    # Environment ゾーンの条件評価
    if cond.startswith("EnvironmentCount"):
        try:
            if ">=" in cond:
                n = int(cond.split(">=",1)[1])
                env_count = sum(1 for c in item["cards"] if c["zone"] == "Environment")
                return env_count >= n
            elif "==" in cond:
                n = int(cond.split("==",1)[1])
                env_count = sum(1 for c in item["cards"] if c["zone"] == "Environment")
                return env_count == n
            elif "<=" in cond:
                n = int(cond.split("<=",1)[1])
                env_count = sum(1 for c in item["cards"] if c["zone"] == "Environment")
                return env_count <= n
        except ValueError:
            print(f"  Invalid condition format: {cond}")
            return False
    
    # ターン数の条件評価
    if cond.startswith("TurnCount"):
        try:
            turn_count = item.get("turnCount", 0)
            if ">=" in cond:
                n = int(cond.split(">=",1)[1])
                return turn_count >= n
            elif "==" in cond:
                n = int(cond.split("==",1)[1])
                return turn_count == n
            elif "<=" in cond:
                n = int(cond.split("<=",1)[1])
                return turn_count <= n
        except ValueError:
            print(f"  Invalid condition format: {cond}")
            return False
    
    # 他の条件式が増えたらここに追加…
    print(f"  Unknown condition: {cond}")
    return False

# ----------------------
#  リーダーのパッシブ オーラ更新
# ----------------------
def refresh_passive_auras(item, events):
    """
    全プレイヤーのリーダーパッシブ効果を再評価し、適用/解除を行う。
    拡張されたゾーンフィルタリングに対応。
    """
    for p in item["players"]:
        _process_leader_passive_effects(p, item, events)


def _process_leader_passive_effects(player, item, events):
    """
    単一プレイヤーのリーダーパッシブ効果を処理する。
    """
    leader_def = get_leader_def(player["leaderId"])
    print(f"Processing leader {player['leaderId']} for player {player['id']}, leader_def: {leader_def}")
    if not leader_def:
        return

    turn_cnt = item.get("turnCount", 0)
    stage_idx = get_stage_index(turn_cnt)
    stages = leader_def.get("evolutionStages", [])
    print(f"  Evolution stage index: {stage_idx} (turn {turn_cnt})")
    if stage_idx >= len(stages):
        return
    stage_def = stages[stage_idx]

    # すべてのパッシブ効果を評価
    print(f"  Evaluating passive effects for stage {stage_idx}")
    for eff in stage_def.get("passiveEffects", []):
        print(f"    Evaluating effect: {eff}")
        _evaluate_and_apply_passive_effect(eff, player, item, events)


def _evaluate_and_apply_passive_effect(effect, player, item, events):
    """
    単一パッシブ効果の条件評価と適用/解除を行う。
    """
    cond = effect.get("condition", "")
    # ここで ownerId を持つダミーカードを渡す
    leader_card = {"id": player["leaderId"], "ownerId": player["id"]}
    
    if evaluate_condition(cond, leader_card, item):
        # 条件成立→付与
        print(f"    Condition met, applying effect: {effect}")
        apply_passive_effect(effect, player, item, events)
    else:
        # 条件不成立→解除
        print(f"    Condition not met, clearing effect: {effect}")
        clear_passive_from_targets(effect, player, item, events)


def _convert_to_battle_buff(action):
    """
    アクションをbattle_buffアクションに変換する。
    パッシブ効果での状態変更をbattle_buff経由で処理するため。
    """
    action_type = action.get("type", "")
    
    # オーラ系アクションをbattle_buffに変換
    if action_type in ["PowerAura", "DamageAura", "KeywordAura"]:
        keyword_mapping = {
            "PowerAura": "Power",
            "DamageAura": "Damage",
            "KeywordAura": action.get("keyword", "Power")
        }
        
        return {
            "type": "BattleBuff",
            "target": action.get("target", "Self"),
            "keyword": keyword_mapping.get(action_type, action.get("keyword", "Power")),
            "value": action.get("value", 0),
            "duration": action.get("duration", -1)  # パッシブ効果は基本的に永続
        }
    
    # 既にbattle_buffの場合はそのまま
    if action_type == "BattleBuff":
        return action
    
    # その他のアクションはそのまま（移動系など）
    return action


def _get_target_zones_from_action(action):
    """
    アクションの target 設定から対象となるゾーンを取得する。
    """
    target = action.get("target", "")
    if "Field" in target:
        return ["Field"]
    elif "Environment" in target:
        return ["Environment"]
    elif "Counter" in target:
        return ["Counter"]
    elif "Hand" in target:
        return ["Hand"]
    elif "Graveyard" in target:
        return ["Graveyard"]
    elif "ExileZone" in target:
        return ["ExileZone"]
    elif "DamageZone" in target:
        return ["DamageZone"]
    elif "Deck" in target:
        return ["Deck"]
    else:
        return ["Unknown"]


def apply_passive_effect(eff, player, item, events):
    """
    パッシブ効果を対象カードに適用する。
    拡張されたゾーンフィルタリングに対応。
    PowerAura/DamageAuraは直接ハンドラを使用してtempStatusesにセット。
    """
    dummy = {"id": player["leaderId"], "ownerId": player["id"]}
    
    for act in eff.get("actions", []):
        # 対象カード取得（拡張されたゾーン対応）
        targets = resolve_targets(dummy, act, item)
        target_zones = _get_target_zones_from_action(act)
        
        print(f"      Applying passive effect to {len(targets)} targets in zones: {target_zones}")
        print(f"      Target IDs: {[t['id'] for t in targets]}")
        
        # アビリティ発動ログ
        events.append({
            "type": "AbilityActivated",
            "payload": {
                "sourceCardId": dummy["id"], 
                "trigger": eff.get("trigger", "Passive"),
                "targetZones": target_zones,
                "targetCount": len(targets)
            }
        })
        
        # PowerAura/DamageAuraの場合は直接ハンドラを使用
        if act.get("type") in ["PowerAura", "DamageAura"]:
            # 直接アクションハンドラを呼び出し
            events.extend(apply_action(dummy, act, item, player["id"]))
        else:
            # その他のアクションはbattle_buffに変換して実行
            battle_buff_action = _convert_to_battle_buff(act)
            # パッシブ効果のソースカードIDを追加
            battle_buff_action["sourceCardId"] = dummy["id"]
            
            # 実際に付与
            for tgt in targets:
                events.extend(apply_action(tgt, battle_buff_action, item, player["id"]))


def clear_passive_from_targets(eff, player, item, events):
    """
    以前に付与したパッシブ効果を外す。
    拡張されたゾーンフィルタリングに対応。
    PowerAura/DamageAuraは直接ハンドラで適用された効果をクリア。
    """
    dummy = {"id": player["leaderId"], "ownerId": player["id"]}
    
    for act in eff.get("actions", []):
        # PowerAura/DamageAuraの場合は直接キーワードを取得
        if act.get("type") == "PowerAura":
            k = "Power"
            k_mapped = keyword_map(k)  # TempPowerBoost
        elif act.get("type") == "DamageAura":
            k = "Damage"
            k_mapped = keyword_map(k)  # TempDamageBoost
        else:
            # その他のアクションはbattle_buffに変換してキーワードを取得
            battle_buff_action = _convert_to_battle_buff(act)
            k = battle_buff_action.get("keyword", "Power")
            k_mapped = keyword_map(k)
        
        # 対象カード取得（拡張されたゾーン対応）
        targets = resolve_targets(dummy, act, item)
        target_zones = _get_target_zones_from_action(act)
        
        print(f"      Clearing passive effect from {len(targets)} targets in zones: {target_zones}")
        print(f"      Target IDs: {[t['id'] for t in targets]}")

        for tgt in targets:
            # PowerAura/DamageAuraは一時ステータスをクリア（expire_turn=-1で永続だが、tempStatusesに入っている）
            _clear_temp_statuses(tgt, k_mapped, dummy["id"], k, events)


def _clear_temp_statuses(target, keyword_mapped, source_id, keyword, events):
    """
    対象カードから一時ステータスを削除する。
    """
    before = len(target.get("tempStatuses", []))
    target["tempStatuses"] = [
        s for s in target.get("tempStatuses", [])
        if not (s["key"] == keyword_mapped and s["sourceId"] == source_id)
    ]
    if len(target.get("tempStatuses", [])) < before:
        events.append({
            "type": "BattleBuffRemoved",
            "payload": {
                "cardId": target["id"],
                "keyword": keyword,
                "sourceCardId": source_id
            }
        })


def _clear_permanent_statuses(target, keyword_mapped, source_id, keyword, events):
    """
    対象カードから恒常ステータスを削除する。
    """
    before = len(target.get("statuses", []))
    target["statuses"] = [
        v for v in target.get("statuses", [])
        if not (v["key"] == keyword_mapped and v.get("sourceId") == source_id)
    ]
    if len(target.get("statuses", [])) < before:
        events.append({
            "type": "StatusRemoved",
            "payload": {
                "cardId": target["id"],
                "keyword": keyword,
                "sourceCardId": source_id
            }
        })

# ---------- Phase helper -------------------------------------

def build_phase(old, new, cur, nxt, *, draw=False):
    ev = [
        {"type": "TurnEnded", "payload": {"playerId": cur}},
        {"type": "PhaseChanged", "payload": {"phase": new, "playerId": nxt}},
    ]
    if new == "Draw" and draw:
        ev.append({"type": "Draw", "payload": {"playerId": nxt, "count": 1}})
    return ev


def do_draw(item, player_id):
    """山札の先頭1枚を手札へ。引けなければ pass"""
    for c in item["cards"]:
        if c["ownerId"] == player_id and c["zone"] == "Deck":
            c["zone"] = "Hand"
            return True  # 1 枚動かした
    return False


# ---------- Card 検索 ---------------------------------------

def find_card(item, card_id):
    """指定されたカードIDに一致するカードを検索"""
    return next((c for c in item["cards"] if c["id"] == card_id), None)


# ------------------------------------------------------------
#  Resolve step helper
# ------------------------------------------------------------

def calc_total_power(card):
    """元データ + TempPowerBoost をざっくり合算"""
    base = int(card.get("power", 0))
    for s in card.get("tempStatuses", []):
        if s["key"] == "TempPowerBoost":
            base += int(s["value"])
    return base


def resolve_battle(item, events):
    """
    pendingBattle を見て、Destroy / Damage などのイベントを追加し
    battleStep を CleanUp へ進める
    """
    pb = item.get("pendingBattle") or {}
    atk = find_card(item, pb.get("attackerId"))
    tgt_id = pb.get("blockerId") or pb.get("targetId")
    tgt = find_card(item, tgt_id) if tgt_id else None
    is_leader = pb.get("isLeader", False) and not tgt  # blocker がいる場合は False

    if not atk:
        item["battleStep"] = "CleanUp"
        return

    destroy_ids = []
    # ----- ① リーダー攻撃の場合 -----
    if is_leader:
        dmg = int(atk.get("damage", 0))
        events.append({
            "type": "Damage",
            "payload": {"playerId": pb["targetOwnerId"], "amount": dmg},
        })

    # ----- ② ユニット vs ユニット の場合 -----
    else:
        atk_pow = calc_total_power(atk)
        tgt_pow = calc_total_power(tgt)

        if atk_pow > tgt_pow:  # 勝ち
            destroy_ids.append(tgt["id"])
            if atk.get("IsCritical"):
                overflow = atk_pow - tgt_pow - int(tgt.get("damage", 0))
                if overflow > 0:
                    events.append({
                        "type": "Damage",
                        "payload": {"playerId": tgt["ownerId"], "amount": overflow},
                    })
        elif atk_pow < tgt_pow:  # 負け
            destroy_ids.append(atk["id"])
        else:  # 相打ち
            destroy_ids += [atk["id"], tgt["id"]]

    # ----- ③ 破壊イベント -----
    for cid in destroy_ids:
        crd = find_card(item, cid)
        if crd and crd["zone"] == "Field":
            crd["zone"] = "Graveyard"
    if destroy_ids:
        events.append({"type": "Destroy", "payload": {"cardIds": destroy_ids}})

# ----------------------
#  リーダー処理
# ----------------------
def get_leader_def(leader_id: str) -> dict | None:
    """leaderId ('leader_001' 形式) からマスターデータをキャッシュ付きで取得"""
    if leader_id not in leader_cache:
        resp = leader_table.get_item(Key={"leaderId": leader_id})
        leader_cache[leader_id] = resp.get("Item")
    return leader_cache[leader_id]

def get_stage_index(turn_count: int) -> int:
    """0-based の進化ステージインデックスを返す"""
    for idx, threshold in enumerate(EVOLVE_THRESHOLDS):
        if turn_count < threshold:
            return idx
    return len(EVOLVE_THRESHOLDS)

# =================== Lambda ENTRY =============================
def lambda_handler(event, context):
    field=event["info"]["fieldName"]; args=event.get("arguments",{})
    logger.info("Field %s  Args %s", field, args)

    # publishClientUpdate そのまま返す
    if field=="publishClientUpdate":
        return {**args, "timestamp": now_iso()}

    # マッチ読み込み - 安全な処理
    mid = args.get("matchId") or args.get("id")
    if not mid:
        # マッチIDがない場合は適切なエラーレスポンスを返す
        return {
            "match": None,
            "events": [{
                "type": "MissingMatchId",
                "payload": {
                    "message": "マッチIDが必要です"
                }
            }]
        }
    
    item = table.get_item(Key={"pk": mid, "sk": "STATE"}).get("Item")
    if not item:
        # マッチが見つからない場合は適切なエラーレスポンスを返す
        return {
            "match": None,
            "events": [{
                "type": "MatchNotFound",
                "payload": {
                    "matchId": mid,
                    "message": "指定されたマッチが見つかりません"
                }
            }]
        }

    # -------- getMatch ----------------------------------------
    if field == "getMatch":
        match_id = args["id"]
        resp     = table.get_item(Key={"pk": match_id, "sk": "STATE"})
        item     = resp.get("Item")
        return json.loads(json.dumps(item, cls=DecimalEncoder)) if item else None

    # -------- moveCards ---------------------------------------
    if field=="moveCards":
        print(f"MoveCards: {args}")
        trig=[]
        for mv in args.get("moves",[]):
            cid,toz = mv["cardId"],mv["toZone"]
            card=next((c for c in item["cards"] if c["id"]==cid),None)
            if not card: continue
            fromz=card["zone"]; card["zone"]=toz
            if fromz=="Field" and toz!="Field": detach_auras(card,item["cards"])
            if fromz=="Hand" and toz=="Field":
                trig.append({"type":"OnPlay","payload":{"cardId":cid}})
            if toz=="Field":
                trig.append({"type":"OnEnterField","payload":{"cardId":cid}})

        evs=resolve(trig,item)
        
        item["updatedAt"]=now_iso()
        bump(item)
        refresh_passive_auras(item, evs)
        table.put_item(Item=item)
        return {"match":json.loads(json.dumps(item,cls=DecimalEncoder)),
                "events":evs}

    # -------- summonCard --------------------------------------
    if field=="summonCard":
        print(f"SummonCard: {args}")
        cid = args.get("cardId")
        if not cid:
            # カードIDがない場合は何もしない
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": []}
        
        card = next((c for c in item["cards"] if c["id"]==cid), None)
        if not card:
            # カードが見つからない場合はエラーイベントを返す
            error_event = {
                "type": "CardNotFound",
                "payload": {
                    "cardId": cid,
                    "message": "指定されたカードが見つかりません"
                }
            }
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}
        
        if card["zone"] == "Field":
            # 既にフィールドにある場合はエラーイベントを返す
            error_event = {
                "type": "AlreadyOnField",
                "payload": {
                    "cardId": cid,
                    "message": "カードは既にフィールドに存在します"
                }
            }
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}
        detach_auras(card,item["cards"])
        card["zone"]="Field"
        trig=[{"type":"OnSummon","payload":{"cardId":cid}},
              {"type":"OnEnterField","payload":{"cardId":cid}}]
        evs=resolve(trig,item)
        
        item["updatedAt"]=now_iso()
        bump(item)
        refresh_passive_auras(item, evs)
        table.put_item(Item=item)
        return {"match":json.loads(json.dumps(item,cls=DecimalEncoder)),
                "events":evs}

    # -------- advancePhase / endTurn --------------------------
    if field in ("advancePhase", "endTurn"):
        cur = item["turnPlayerId"]
        # 次のターンプレイヤーを決定
        nxt = next(p for p in item["players"] if p["id"] != cur)

        seq = ["Start", "Draw", "Main", "End"]
        old = item.get("phase", "Start")
        new = seq[(seq.index(old) + 1) % len(seq)]

        # End → Start でターンプレイヤー交代
        if new == "Start":
            # ターンチェンジの前にターン数をインクリメント（End フェーズ後）
            if old == "End":
                item["turnCount"] = item.get("turnCount", 0) + 1
                clear_expired(item["cards"], item["turnCount"])
                # 攻撃フラグリセット
                for c in item["cards"]:
                    if c["ownerId"] == item["turnPlayerId"] and c["zone"] == "Field":
                        add_status(c, "HasAttacked", False)
            # プレイヤー切り替え
            item["turnPlayerId"] = nxt["id"]

        # 基本イベント
        events = [
            {"type": "TurnEnded",    "payload": {"playerId": cur}},
            {"type": "PhaseChanged", "payload": {"phase": new, "playerId": item["turnPlayerId"]}}
        ]
        item["phase"] = new

        # 新ターン Start フェーズでリーダーパッシブ適用
        if new == "Start":
            refresh_passive_auras(item, events)

            # ターンプレイヤーに {"color": "COLORLESS", "isUsed": False} を追加し、isUsed をすべて False に設定
            turn_player = next(p for p in item["players"] if p["id"] == item["turnPlayerId"])
            turn_player.setdefault("levelPoints", []).append({"color": "COLORLESS", "isUsed": False})
            for point in turn_player["levelPoints"]:
                point["isUsed"] = False

        # Draw フェーズを即処理して Main へ
        if new == "Draw":
            if item.get("turnCount", 0) == 0 or not do_draw(item, item["turnPlayerId"]):
                events.append({"type": "Draw", "payload": {"playerId": item["turnPlayerId"], "count": 0}})
            else:
                events.append({"type": "Draw", "payload": {"playerId": item["turnPlayerId"], "count": 1}})

            # Draw 完了 → Main
            new = "Main"
            item["phase"] = "Main"
            events.append({
                "type": "PhaseChanged",
                "payload": {"phase": "Main", "playerId": item["turnPlayerId"]}
            })

        # 永続化＆AI起動
        item["updatedAt"] = now_iso()
        bump(item)
        table.put_item(Item=item)

        ai_turn = nxt["name"].startswith("AI_")
        if new == "Start" and ai_turn:
            ai.invoke(
                FunctionName=os.environ["AI_LAMBDA_NAME"],
                InvocationType="Event",
                Payload=json.dumps({
                    "matchId":   mid,
                    "playerId":  nxt["id"],
                    "matchItem": json.loads(json.dumps(item, cls=DecimalEncoder))
                }).encode('utf-8')
            )

        return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": events}
    
    # --- declareAttack -----------------------------------
    if field == "declareAttack":
        cid_a = args.get("attackerId")
        cid_t = args.get("targetId")
        is_leader = args.get("targetIsLeader", False)

        # 1) フィールドチェック - 安全な処理
        if not cid_a:
            # 攻撃者IDがない場合は何もしない
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": []}
        
        attacker = find_card(item, cid_a)
        if not attacker or attacker["zone"] != "Field":
            # 攻撃者が無効な場合はエラーイベントを返す
            error_event = {
                "type": "InvalidAttacker",
                "payload": {
                    "attackerId": cid_a,
                    "message": "攻撃者が無効です（存在しないかフィールドにいません）"
                }
            }
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}

        if not is_leader:
            target = find_card(item, cid_t)
            if not target or target["zone"] != "Field":
                # ターゲットが無効な場合はエラーイベントを返す
                error_event = {
                    "type": "InvalidTarget",
                    "payload": {
                        "targetId": cid_t,
                        "message": "ターゲットが無効です（存在しないかフィールドにいません）"
                    }
                }
                return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}
        else:
            target = None

        # 2) まず防御側プレイヤーを取得しておく（AI 判定にも使う）
        defender = next(p for p in item["players"] if p["id"] != attacker["ownerId"])

        # 3) pendingBattle をセット
        item["pendingBattle"] = {
            "attackerId":      cid_a,
            "attackerOwnerId": attacker["ownerId"],
            "targetId":        cid_t,
            "targetOwnerId":   (target["ownerId"] if target else defender["id"]),
            "blockerId":       None,
            "isLeader":        is_leader,
        }
        item["battleStep"] = "BlockChoice"

        # 4) 攻撃宣言イベント
        events = [{
            "type": "AttackDeclared",
            "payload": {
                "attackerId": cid_a,
                "targetId"  : cid_t,
                "isLeader"  : is_leader
            }
        }]

        # 5) 相手が AI なら
        defender = next(p for p in item["players"] if p["id"] != attacker["ownerId"])
        if defender["name"].startswith("AI_"):
            # ❶ ノーブロックを即決
            item["pendingBattle"]["blockerId"] = None
            events.append({
            "type": "BlockSet",
            "payload": {"blockerId": None}
            })

            # ❷ 「AttackAbility」段階をスキップし、そのまま Resolve へ
            item["battleStep"] = "Resolve"

            # ❸ Destroy / Damage を計算して events に追加
            resolve_battle(item, events)          # CleanUp へは進めない

        else:
            # 人間プレイヤーがブロックを選ぶ場合は従来どおり
            item["battleStep"] = "AttackAbility"

        # **ここでカウンター発動の選択肢を追加**
        # defender = 攻撃されたプレイヤー
        # カウンターゾーンにカードがある場合は、カウンターを発動するか選択肢を出す
        if any(c for c in item["cards"] if c["ownerId"] == defender["id"] and c["zone"] == "Counter"):  
            req_id = str(now_iso())
            item.setdefault("choiceRequests", []).append({
                "requestId":  req_id,
                "playerId":   defender["id"],
                "promptText": "カウンターを発動しますか？",
                "options":    ["Yes", "No"]
            })

        bump(item)
        item["updatedAt"] = now_iso()
        table.put_item(Item=item)

        return {
            "match":  json.loads(json.dumps(item, cls=DecimalEncoder)),
            "events": events
        }

    if field == "setBlocker":
        bid = args.get("blockerId")      # None = ノーブロック
        pb  = item.get("pendingBattle") or {}
        
        # バトルステップの安全な確認
        if item.get("battleStep") != "BlockChoice":
            error_event = {
                "type": "InvalidBattleStep",
                "payload": {
                    "currentStep": item.get("battleStep"),
                    "message": "ブロック選択段階ではありません"
                }
            }
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}

        if bid:
            blk = find_card(item, bid)
            if not blk or blk["ownerId"] == pb.get("attackerOwnerId"):
                # 無効なブロッカーの場合はエラーイベントを返す
                error_event = {
                    "type": "InvalidBlocker",
                    "payload": {
                        "blockerId": bid,
                        "message": "無効なブロッカーです（存在しないか攻撃者と同じプレイヤーです）"
                    }
                }
                return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}
        pb["blockerId"] = bid
        item["pendingBattle"] = pb
        item["battleStep"]    = "AttackAbility"

        events = [{"type": "BlockSet",
                "payload": {"blockerId": bid}}]

        bump(item); item["updatedAt"] = now_iso()
        table.put_item(Item=item)
        return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)),
                "events": events}

    # -------- resolveBattle ----------------------------------
    if field == "resolveBattle":
        # AttackAbility → Resolve をクライアントが要求
        if item.get("battleStep") != "AttackAbility":
            error_event = {
                "type": "InvalidBattleStep",
                "payload": {
                    "currentStep": item.get("battleStep"),
                    "message": "アビリティ発動段階ではありません"
                }
            }
            return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)), "events": [error_event]}

        events = []
        resolve_battle(item, events)      # Destroy / Damage を積む

        item["battleStep"] = "Resolve"    # ここでは CleanUp へ進めない
        bump(item); item["updatedAt"] = now_iso()
        table.put_item(Item=item)

        return {
            "match":  json.loads(json.dumps(item, cls=DecimalEncoder)),
            "events": events
        }

    if field == "resolveAck":
        if item.get("battleStep") == "Resolve":
            pb  = item.get("pendingBattle") or {}
            atk = find_card(item, pb.get("attackerId"))
            if atk:
                add_status(atk, "HasAttacked", True)

            item["pendingBattle"] = None
            item["battleStep"]    = "CleanUp"

        bump(item); item["updatedAt"] = now_iso()
        table.put_item(Item=item)

        return {"match": json.loads(json.dumps(item, cls=DecimalEncoder)),
                "events": []}


    # ──────────────── その他 Mutation 群 ────────────────
    if field == "setTurnPlayer":
        item["turnPlayerId"] = args["playerId"]; item["updatedAt"] = now_iso()
        bump(item); table.put_item(Item=item)
        return json.loads(json.dumps(item, cls=DecimalEncoder))

    if field == "updatePhase":
        item["phase"] = args["phase"]; item["updatedAt"] = now_iso()
        bump(item); table.put_item(Item=item)
        return json.loads(json.dumps(item, cls=DecimalEncoder))

    if field == "sendChoiceRequest":
        body = json.loads(args["json"])
        item.setdefault("choiceRequests", []).append(body)
        item["updatedAt"] = now_iso(); bump(item); table.put_item(Item=item)
        return json.loads(json.dumps(item, cls=DecimalEncoder))

    if field == "submitChoiceResponse":
        body = json.loads(args["json"])
        item.setdefault("choiceResponses", []).append(body)
        item["updatedAt"] = now_iso(); bump(item); table.put_item(Item=item)
        return json.loads(json.dumps(item, cls=DecimalEncoder))

    if field == "updateCardStatuses":
        for upd in args.get("updates", []):
            cid, key, val = upd["instanceId"], upd["key"], upd["value"]
            card = next((c for c in item["cards"] if c["id"] == cid), None)
            if not card: continue
            add_status(card, key, val)
        item["updatedAt"] = now_iso(); bump(item); table.put_item(Item=item)
        return {"success": True, "errorMessage": None}

    if field == "updateLevelPoints":
        print(f"UpdateLevelPoints: {args}")

        # ① JSON文字列をパース
        raw_points = json.loads(args["json"])  # 例: [{"Color":0,"IsUsed":false}, …]

        # ② 大文字キーを小文字キーに正規化し、数値インデックスを enum 名に変換
        enum_names = ["COLORLESS", "RED", "BLUE", "GREEN", "YELLOW", "BLACK"]
        new_points = []
        for p in raw_points:
            idx = p.get("Color", p.get("color"))
            name = enum_names[int(idx)]  # idx が文字列なら int() で変換
            new_points.append({
            "color":  name,                # ← 文字列で書き込む
            "isUsed": p.get("IsUsed", p.get("isUsed"))
            })

        # ③ プレイヤー識別用の引数チェック
        target_player_id = args.get("playerId")
        if not target_player_id:
            raise Exception("playerId is required")

        # ④ players リストから該当プレイヤーを探して levelPoints を更新
        updated = False
        for player in item["players"]:
            if player.get("id") == target_player_id:
                player["levelPoints"] = new_points
                updated = True
                break

        if not updated:
            raise Exception(f"Player {target_player_id} not found in match {item['id']}")

        # ⑤ updatedAt を更新してテーブルに保存
        item["updatedAt"] = now_iso()
        bump(item)
        table.put_item(Item=item)

        # ⑥ 必要なフィールドだけ返却
        return {
            "id":           item["id"],
            "matchVersion": item["matchVersion"],
            "phase":        item.get("phase"),
            "status":       item.get("status"),
            "turnPlayerId": item.get("turnPlayerId"),
            "updatedAt":    item["updatedAt"]
        }

    # 未サポート - 安全な処理
    return {
        "match": json.loads(json.dumps(item, cls=DecimalEncoder)),
        "events": [{
            "type": "UnsupportedField",
            "payload": {
                "field": field,
                "message": f"サポートされていないフィールドです: {field}"
            }
        }]
    }