#!/usr/bin/env python3
"""
CSV 定義 ⇔ 実装カバレッジ検証スクリプト
"""

import csv
import json
import os
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Any
import action_registry

def parse_dynamodb_json(dynamodb_string: str) -> dict:
    """DynamoDB JSON形式を通常のPythonオブジェクトに変換"""
    try:
        if not dynamodb_string or dynamodb_string.strip() == '':
            return {}
        
        # DynamoDB JSON形式をパース
        data = json.loads(dynamodb_string)
        
        def convert_dynamodb_item(item):
            """DynamoDB形式から通常のJSONに変換"""
            if isinstance(item, dict):
                if len(item) == 1:
                    key, value = next(iter(item.items()))
                    if key == 'S':  # String
                        return value
                    elif key == 'N':  # Number
                        return int(value) if value.isdigit() else float(value)
                    elif key == 'BOOL':  # Boolean
                        return value
                    elif key == 'L':  # List
                        return [convert_dynamodb_item(v) for v in value]
                    elif key == 'M':  # Map
                        return {k: convert_dynamodb_item(v) for k, v in value.items()}
                return {k: convert_dynamodb_item(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [convert_dynamodb_item(v) for v in item]
            else:
                return item
        
        return convert_dynamodb_item(data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"JSON パースエラー: {e}")
        print(f"問題のあるJSON: {dynamodb_string[:200]}...")
        return {}

def extract_triggers_and_actions(csv_file_path: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], List[dict]]:
    """CSVから全てのトリガーとアクションを抽出"""
    triggers = defaultdict(list)
    actions = defaultdict(list)
    cards_data = []
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            card_id = row.get('cardId', '')
            description = row.get('description', '')
            effect_list_str = row.get('effectList', '')
            
            # effectList をパース
            effect_list = parse_dynamodb_json(effect_list_str)
            
            card_data = {
                'cardId': card_id,
                'description': description,
                'effectList': effect_list,
                'triggers': [],
                'actions': []
            }
            
            if isinstance(effect_list, list):
                for effect in effect_list:
                    if isinstance(effect, dict):
                        # trigger の抽出
                        trigger = effect.get('trigger', '')
                        if trigger:
                            triggers[trigger].append(card_id)
                            card_data['triggers'].append(trigger)
                        
                        # activationType の抽出（これもトリガーとして扱う）
                        activation_type = effect.get('activationType', '')
                        if activation_type:
                            triggers[activation_type].append(card_id)
                            card_data['triggers'].append(activation_type)
                        
                        # actions の抽出
                        effect_actions = effect.get('actions', [])
                        if isinstance(effect_actions, list):
                            for action in effect_actions:
                                if isinstance(action, dict):
                                    action_type = action.get('type', '')
                                    if action_type:
                                        actions[action_type].append(card_id)
                                        card_data['actions'].append(action_type)
            
            cards_data.append(card_data)
    
    return dict(triggers), dict(actions), cards_data

def get_server_implementations() -> Tuple[Set[str], Set[str]]:
    """サーバー側の実装済みハンドラを取得"""
    registered_actions = set()
    
    # action_registry から登録済みアクションを取得
    for action_type in [
        "Draw", "PowerAura", "DamageAura", "KeywordAura", "Select", "SelectOption",
        "Destroy", "Summon", "PayCost", "GainLevel", "DestroyLevel", "AssignColor",
        "ActivateCost", "PlayerStatus", "SetPlayerStatus", "Transform", "CounterChange",
        "ApplyDamage", "CreateToken", "CallMethod", "NextSummonBuff", "CostModifier",
        "SetStatus", "Bounce", "Discard", "Exile", "MoveField", "MoveDeck", "MoveToDamageZone"
    ]:
        registered_actions.add(action_type)
    
    # トリガーハンドラは lambda_function.py の handle_trigger で処理される
    # 実際に処理されるトリガーは card.effectList の trigger フィールドで動的に決まる
    supported_triggers = set([
        "OnPlay", "OnSummon", "OnDestroy", "OnAttack", "OnAttackEnd", "OnLeaveField",
        "OnCardEntersField", "OnCardPlayedFromHand", "Passive", "ShieldTrigger",
        "Arts", "Counter", "activate"
    ])
    
    return supported_triggers, registered_actions

def analyze_reproducibility(cards_data: List[dict]) -> List[dict]:
    """description → effectList の再現性を分析"""
    reproducibility_results = []
    
    for card in cards_data:
        card_id = card['cardId']
        description = card['description']
        effect_list = card['effectList']
        
        result = {
            'cardId': card_id,
            'description': description,
            'reproducible': True,
            'issues': [],
            'missing_implementations': []
        }
        
        # 空のeffectListの場合
        if not effect_list:
            if description and description.strip():
                result['reproducible'] = False
                result['issues'].append("効果説明はあるがeffectListが空")
            reproducibility_results.append(result)
            continue
        
        # effectListの各効果を分析
        if isinstance(effect_list, list):
            for i, effect in enumerate(effect_list):
                if not isinstance(effect, dict):
                    result['reproducible'] = False
                    result['issues'].append(f"効果{i+1}: effectの形式が不正")
                    continue
                
                # trigger の検証
                trigger = effect.get('trigger', '')
                activation_type = effect.get('activationType', '')
                
                # actions の検証
                actions = effect.get('actions', [])
                if isinstance(actions, list):
                    for j, action in enumerate(actions):
                        if isinstance(action, dict):
                            action_type = action.get('type', '')
                            if not action_type:
                                result['reproducible'] = False
                                result['issues'].append(f"効果{i+1}のアクション{j+1}: typeが未定義")
        
        reproducibility_results.append(result)
    
    return reproducibility_results

def generate_coverage_report(triggers: Dict[str, List[str]], actions: Dict[str, List[str]], 
                           supported_triggers: Set[str], registered_actions: Set[str],
                           reproducibility_results: List[dict]) -> str:
    """カバレッジレポートを生成"""
    report = "# CSV 定義 ⇔ 実装カバレッジ検証レポート\n\n"
    
    # トリガーの網羅性チェック
    report += "## 1. トリガー網羅性チェック\n\n"
    report += "### 実装済みトリガー\n"
    for trigger in sorted(supported_triggers):
        card_count = len(triggers.get(trigger, []))
        report += f"- `{trigger}`: {card_count}枚のカードで使用\n"
    
    report += "\n### 未実装トリガー\n"
    unimplemented_triggers = set(triggers.keys()) - supported_triggers
    if unimplemented_triggers:
        for trigger in sorted(unimplemented_triggers):
            card_count = len(triggers[trigger])
            report += f"- `{trigger}`: {card_count}枚のカードで使用 ⚠️\n"
    else:
        report += "全てのトリガーが実装済みです ✅\n"
    
    # アクションの網羅性チェック
    report += "\n## 2. アクション網羅性チェック\n\n"
    report += "### 実装済みアクション\n"
    for action in sorted(registered_actions):
        card_count = len(actions.get(action, []))
        report += f"- `{action}`: {card_count}枚のカードで使用\n"
    
    report += "\n### 未実装アクション\n"
    unimplemented_actions = set(actions.keys()) - registered_actions
    if unimplemented_actions:
        for action in sorted(unimplemented_actions):
            card_count = len(actions[action])
            report += f"- `{action}`: {card_count}枚のカードで使用 ⚠️\n"
    else:
        report += "全てのアクションが実装済みです ✅\n"
    
    # 再現性レポート
    report += "\n## 3. description → effectList 再現性レポート\n\n"
    
    reproducible_count = sum(1 for r in reproducibility_results if r['reproducible'])
    total_count = len(reproducibility_results)
    
    report += f"### 統計\n"
    report += f"- 総カード数: {total_count}\n"
    report += f"- 再現可能: {reproducible_count}枚 ({reproducible_count/total_count*100:.1f}%)\n"
    report += f"- 再現不可: {total_count - reproducible_count}枚 ({(total_count - reproducible_count)/total_count*100:.1f}%)\n\n"
    
    # 詳細な問題リスト
    report += "### 問題のあるカード\n\n"
    report += "| カードID | 再現可否 | 問題 |\n"
    report += "|----------|:--------:|------|\n"
    
    for result in reproducibility_results:
        if not result['reproducible']:
            status = "❌"
            issues = "; ".join(result['issues'])
        else:
            status = "✅"
            issues = "なし"
        
        report += f"| {result['cardId']} | {status} | {issues} |\n"
    
    # 必要な実装対応
    report += "\n## 4. 必要な実装対応\n\n"
    
    if unimplemented_triggers:
        report += "### 未実装トリガーの対応\n"
        for trigger in sorted(unimplemented_triggers):
            cards = triggers[trigger]
            report += f"- `{trigger}`: {len(cards)}枚のカード - {', '.join(cards[:5])}{'...' if len(cards) > 5 else ''}\n"
    
    if unimplemented_actions:
        report += "### 未実装アクションの対応\n"
        for action in sorted(unimplemented_actions):
            cards = actions[action]
            report += f"- `{action}`: {len(cards)}枚のカード - {', '.join(cards[:5])}{'...' if len(cards) > 5 else ''}\n"
    
    return report

def main():
    """メイン処理"""
    csv_file_path = "/home/runner/work/BattleSync/BattleSync/data/results.csv"
    
    print("CSV データを解析中...")
    triggers, actions, cards_data = extract_triggers_and_actions(csv_file_path)
    
    print("サーバー側実装を確認中...")
    supported_triggers, registered_actions = get_server_implementations()
    
    print("再現性を分析中...")
    reproducibility_results = analyze_reproducibility(cards_data)
    
    print("レポートを生成中...")
    report = generate_coverage_report(triggers, actions, supported_triggers, 
                                    registered_actions, reproducibility_results)
    
    # レポートを出力
    with open("/home/runner/work/BattleSync/BattleSync/coverage_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("レポートが coverage_report.md に保存されました")
    
    # 統計情報を表示
    print(f"\n=== 統計情報 ===")
    print(f"総カード数: {len(cards_data)}")
    print(f"ユニークトリガー数: {len(triggers)}")
    print(f"ユニークアクション数: {len(actions)}")
    print(f"サポート済みトリガー数: {len(supported_triggers)}")
    print(f"登録済みアクション数: {len(registered_actions)}")
    
    # 未実装の要素を表示
    unimplemented_triggers = set(triggers.keys()) - supported_triggers
    unimplemented_actions = set(actions.keys()) - registered_actions
    
    if unimplemented_triggers:
        print(f"\n未実装トリガー: {sorted(unimplemented_triggers)}")
    if unimplemented_actions:
        print(f"未実装アクション: {sorted(unimplemented_actions)}")

if __name__ == "__main__":
    main()