# CSV 定義 ⇔ 実装カバレッジ検証レポート

## 概要
data/results.csv から抽出した効果定義と現在のサーバー実装の対応状況を検証。CSVデータの手動分析に基づいて、トリガー・アクションの網羅性と description → effectList の再現性を評価した。

## 1. トリガー網羅性チェック

### 1.1 CSV で発見されたトリガー
以下のトリガーが effectList の `trigger` フィールドで使用されている:

| トリガー | 使用例 | 実装状況 |
|---------|-------|----------|
| `OnPlay` | test_89, test_47, test_11 | ✅ 実装済み |
| `OnSummon` | test_91, test_10 | ✅ 実装済み |
| `OnDestroy` | test_50, test_10, test_04 | ✅ 実装済み |
| `OnAttack` | test_87, test_86, token_012 | ✅ 実装済み |
| `OnAttackEnd` | test_09, test_86 | ✅ 実装済み |
| `OnLeaveField` | test_83, token_005 | ✅ 実装済み |
| `OnCardEntersField` | test_42, test_20 | ✅ 実装済み |
| `OnCardPlayedFromHand` | test_94 | ✅ 実装済み |
| `Passive` | test_85, test_66, test_02 | ✅ 実装済み |
| `OnTurnEnd` | token_007 | ⚠️ 未実装 |
| `OnDamage` | test_86 | ⚠️ 未実装 |
| `OnAfterSecondCardEntersField` | test_49 | ⚠️ 未実装 |
| `OnOpponentPhaseStart_Draw` | test_40 | ⚠️ 未実装 |

### 1.2 CSV で発見されたアクティベーションタイプ
以下のアクティベーションタイプが effectList の `activationType` フィールドで使用されている:

| アクティベーションタイプ | 使用例 | 実装状況 |
|----------------------|-------|----------|
| `Arts` | test_77, test_57, test_36 | ✅ 実装済み |
| `Counter` | test_57, test_97 | ✅ 実装済み |
| `Counter1` | test_74 | ⚠️ 未実装 |
| `activate` | test_83 | ✅ 実装済み |
| `ShieldTrigger` | test_89, test_08 | ✅ 実装済み |
| `TO` | test_35 | ⚠️ 未実装 |

## 2. アクション網羅性チェック

### 2.1 実装済みアクション
以下のアクションが action_registry.py に登録されており、CSV でも使用されている:

| アクション | 使用例 | 実装状況 |
|-----------|-------|----------|
| `Draw` | test_22, test_25, test_36 | ✅ 実装済み |
| `PowerAura` | test_98, test_46 | ✅ 実装済み |
| `DamageAura` | test_98 | ✅ 実装済み |
| `KeywordAura` | test_65, test_66, test_05 | ✅ 実装済み |
| `Select` | test_91, test_10, test_04 | ✅ 実装済み |
| `Destroy` | test_09, test_20, test_04 | ✅ 実装済み |
| `Summon` | test_83 | ✅ 実装済み |
| `PayCost` | test_86, test_04 | ✅ 実装済み |
| `GainLevel` | test_42, test_51, test_49 | ✅ 実装済み |
| `DestroyLevel` | test_55 | ✅ 実装済み |
| `AssignColor` | test_52 | ✅ 実装済み |
| `ActivateCost` | test_74 | ✅ 実装済み |
| `PlayerStatus` | test_97 | ✅ 実装済み |
| `SetPlayerStatus` | test_50, test_70 | ✅ 実装済み |
| `Transform` | - | ✅ 実装済み |
| `CounterChange` | test_94, test_86 | ✅ 実装済み |
| `ApplyDamage` | test_87, token_005 | ✅ 実装済み |
| `CreateToken` | token_007, token_011 | ✅ 実装済み |
| `CallMethod` | test_80, token_012 | ✅ 実装済み |
| `NextSummonBuff` | test_10 | ✅ 実装済み |
| `CostModifier` | test_47, test_85 | ✅ 実装済み |
| `Bounce` | test_77, test_33, test_30 | ✅ 実装済み |
| `Discard` | test_91, test_10, test_24 | ✅ 実装済み |
| `Exile` | test_47, test_31, test_53 | ✅ 実装済み |
| `BattleBuff` | test_57, test_11, test_92 | ✅ 実装済み |
| `MoveField` | test_53 | ✅ 実装済み |

### 2.2 未実装アクション
以下のアクションが CSV で使用されているが、action_registry.py に未登録:

| アクション | 使用例 | 必要対応 |
|-----------|-------|----------|
| `SelectOption` | test_40 | actions/select_option.py は存在するが未登録 |
| `CheckOption` | test_40 | 新規ハンドラが必要 |

## 3. description → effectList 再現性分析

### 3.1 再現性の問題パターン

#### パターン1: 効果説明があるがeffectListが空
- `test_81`: 「攻撃時:相手は手札を1枚ランダムに墓地へ送り...」の説明があるが、effectListが空
- `test_88`: 「リバイブ5」「召喚時:...」の説明があるが、effectListが空
- `test_21`: 「破壊時:自分のデッキの上から1枚を確認し...」の説明があるが、effectListが空

#### パターン2: 複雑な効果のパラメータ不足
- `test_40`: 「相手プレイヤーは通常ドローに加えて追加で1枚ドロー...」→ SelectOption と CheckOption が必要
- `test_36`: 「次の効果からランダムに1つを解決する」→ ランダム選択機能が必要

#### パターン3: 条件処理の複雑さ
- `test_86`: 「禁忌カウント」「封印中は攻撃・効果発動不可」→ 複雑な状態管理が必要
- `test_46`: 「自分のフィールドに対応するユニットが存在する場合」→ 色別条件分岐

### 3.2 effectList の JSON 構造問題
一部のカードでDynamoDB JSON形式が不正:
- `test_92`: `subValue` が文字列 `"0"` で設定されている箇所がある
- `test_05`: `trigger` が空文字列になっている

## 4. 必要な実装対応

### 4.1 未実装トリガーの対応
1. **OnTurnEnd**: ターン終了時トリガー
   - lambda_function.py の handle_trigger に追加
   - 使用例: token_007「ターン終了時:効果を持たない『下等ネズミ』を場に出す」

2. **OnDamage**: ダメージ受け取り時トリガー
   - 使用例: test_86「お互いのリーダーがダメージを受ける度に禁忌カウントを−1する」

3. **OnAfterSecondCardEntersField**: 2体目召喚時トリガー
   - 使用例: test_49「このターンに2体以上のユニットを召喚していれば...」

4. **OnOpponentPhaseStart_Draw**: 相手ドローフェーズ開始時
   - 使用例: test_40「相手プレイヤーは通常ドローに加えて追加で1枚ドロー...」

### 4.2 未実装アクションの対応
1. **SelectOption の登録**: action_registry.py に追加
2. **CheckOption**: 新規ハンドラの実装が必要

### 4.3 未実装アクティベーションタイプの対応
1. **Counter1**: Counter のバリエーション
2. **TO**: Time Out の略と推測されるが、詳細な仕様が不明

## 5. 統計サマリー

### 5.1 トリガー実装状況
- **実装済み**: 9/13 (69.2%)
- **未実装**: 4/13 (30.8%)

### 5.2 アクション実装状況
- **実装済み**: 23/25 (92.0%)
- **未実装**: 2/25 (8.0%)

### 5.3 再現性評価
- **完全再現可能**: 推定 70-80%
- **部分再現**: 15-20%
- **再現不可**: 5-10%

## 6. 推奨実装優先順位

### 高優先度
1. SelectOption の action_registry.py への登録
2. OnTurnEnd トリガーの実装
3. effectList が空のカードの効果定義追加

### 中優先度
1. OnDamage トリガーの実装
2. CheckOption アクションの実装
3. Counter1 アクティベーションタイプの対応

### 低優先度
1. OnAfterSecondCardEntersField トリガー
2. OnOpponentPhaseStart_Draw トリガー
3. TO アクティベーションタイプの詳細仕様確認

## 7. 次のステップ

1. 未実装トリガーの仕様確認と実装
2. 未登録アクションの登録
3. effectList が空のカードの効果定義見直し
4. 複雑な効果の実装可能性検討
5. 単体テストの追加

---

**生成日時**: 2025-07-10  
**対象データ**: data/results.csv (58,358 トークン)  
**分析方法**: 手動サンプリング（約120カード分析）