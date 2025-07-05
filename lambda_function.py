# lambda_function.py
import os, json, boto3, logging
from datetime import datetime, timezone
from decimal import Decimal
from importlib import import_module

# --- 自前モジュール -----------------------------------------
from helper import (
    add_status, add_temp_status, keyword_map, d, resolve_targets,
    DecimalEncoder,
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
    今回は PlayerTurnAndSelfFieldCount==N のみ対応例。
    """
    if not cond:
        return True
    # 自分ターンかつ自分フィールド枚数 == N
    if cond.startswith("PlayerTurnAndSelfFieldCount=="):
        try:
            n = int(cond.split("==",1)[1])
        except ValueError:
            return False
        return (item["turnPlayerId"] == card["ownerId"] and
                sum(1 for c in item["cards"]
                    if c["ownerId"] == card["ownerId"] and c["zone"] == "Field") == n)
    # 他の条件式が増えたらここに追加…
    return False

# ----------------------
#  リーダーのパッシブ オーラ更新
# ----------------------
def refresh_passive_auras(item, events):
    for p in item["players"]:
        leader_def = get_leader_def(p["leaderId"])
        print(f"Processing leader {p['leaderId']} for player {p['id']}, leader_def: {leader_def}")
        if not leader_def:
            continue

        turn_cnt = item.get("turnCount", 0)
        stage_idx = get_stage_index(turn_cnt)
        stages = leader_def.get("evolutionStages", [])
        print(f"  Evolution stage index: {stage_idx} (turn {turn_cnt})")
        if stage_idx >= len(stages):
            continue
        stage_def = stages[stage_idx]

        # すべてのパッシブ効果を評価
        print(f"  Evaluating passive effects for stage {stage_idx}")
        for eff in stage_def.get("passiveEffects", []):
            print(f"    Evaluating effect: {eff}")
            cond = eff.get("condition", "")
            # ここで ownerId を持つダミーカードを渡す
            leader_card = {"id": p["leaderId"], "ownerId": p["id"]}
            if evaluate_condition(cond, leader_card, item):
                # 条件成立→付与
                apply_passive_effect(eff, p, item, events)
            else:
                # 条件不成立→解除
                clear_passive_from_targets(eff, p, item, events)


def apply_passive_effect(eff, player, item, events):
    dummy = {"id": player["leaderId"], "ownerId": player["id"]}
    for act in eff.get("actions", []):
        # 対象カード取得
        targets = resolve_targets(dummy, act, item)
        # ログ
        events.append({
            "type": "AbilityActivated",
            "payload": {"sourceCardId": dummy["id"], "trigger": eff.get("trigger", "Passive")}
        })
        # 実際に付与
        for tgt in targets:
            events.extend(apply_action(tgt, act, item, player["id"]))


def clear_passive_from_targets(eff, player, item, events):
    """
    以前に付与したパッシブオーラを外す。
    eff: passiveEffects の M っぽい dict
    player: players リストの要素 (M っぽい dict)
    """
    dummy = {"id": player["leaderId"], "ownerId": player["id"]}
    for act in eff.get("actions", []):
        k = act.get("keyword") or act["type"].replace("Aura","")
        k_mapped = keyword_map(k)
        dur = int(act.get("duration", -1))
        # 対象カード
        targets = resolve_targets(dummy, act, item)

        for tgt in targets:
            # 一時ステータスをクリア
            before = len(tgt.get("tempStatuses", []))
            tgt["tempStatuses"] = [
                s for s in tgt.get("tempStatuses", [])
                if not (s["key"] == k_mapped and s["sourceId"] == dummy["id"])
            ]
            if len(tgt.get("tempStatuses", [])) < before:
                events.append({
                    "type": "BattleBuffRemoved",
                    "payload": {
                        "cardId": tgt["id"],
                        "keyword": k,
                        "sourceCardId": dummy["id"]
                    }
                })

            # 恒常ステータス（dur == -1）もクリア
            if dur == -1:
                before = len(tgt.get("statuses", []))
                tgt["statuses"] = [
                    v for v in tgt.get("statuses", [])
                    if not (v["key"] == k_mapped and v.get("sourceId") == dummy["id"])
                ]
                if len(tgt.get("statuses", [])) < before:
                    events.append({
                        "type": "StatusRemoved",
                        "payload": {
                            "cardId": tgt["id"],
                            "keyword": k,
                            "sourceCardId": dummy["id"]
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

    # マッチ読み込み
    mid=args.get("matchId") or args.get("id")
    if not mid: raise Exception("need matchId/id")
    item=table.get_item(Key={"pk":mid,"sk":"STATE"}).get("Item")
    if not item: raise Exception("match not found")

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
        
        item["updatedAt"]=now_iso(); bump(item); table.put_item(Item=item)
        refresh_passive_auras(item, evs)
        return {"match":json.loads(json.dumps(item,cls=DecimalEncoder)),
                "events":evs}

    # -------- summonCard --------------------------------------
    if field=="summonCard":
        print(f"SummonCard: {args}")
        cid=args["cardId"]
        card=next((c for c in item["cards"] if c["id"]==cid),None)
        if not card: raise Exception("card not found")
        if card["zone"]=="Field": raise Exception("already on field")
        detach_auras(card,item["cards"])
        card["zone"]="Field"
        trig=[{"type":"OnSummon","payload":{"cardId":cid}},
              {"type":"OnEnterField","payload":{"cardId":cid}}]
        evs=resolve(trig,item)
        
        item["updatedAt"]=now_iso(); bump(item); table.put_item(Item=item)
        refresh_passive_auras(item, evs)
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
        cid_a = args["attackerId"]
        cid_t = args.get("targetId")
        is_leader = args["targetIsLeader"]

        # 1) フィールドチェック
        attacker = find_card(item, cid_a)
        if not attacker or attacker["zone"] != "Field":
            raise Exception("invalid attacker")

        if not is_leader:
            target = find_card(item, cid_t)
            if not target or target["zone"] != "Field":
                raise Exception("invalid target")
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
        if item.get("battleStep") != "BlockChoice":
            raise Exception("Not in BlockChoice")

        if bid:
            blk = find_card(item, bid)
            if not blk or blk["ownerId"] == pb["attackerOwnerId"]:
                raise Exception("invalid blocker")
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
            raise Exception("Not in AttackAbility")

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
        item["levelPoints"] = json.loads(args["json"])
        item["updatedAt"] = now_iso(); bump(item); table.put_item(Item=item)
        return {"id": item["id"],
                "matchVersion": item["matchVersion"],
                "phase": item.get("phase"),
                "status": item.get("status"),
                "turnPlayerId": item.get("turnPlayerId"),
                "updatedAt": item["updatedAt"]}

    # 未サポート
    raise Exception(f"Unsupported field: {field}")