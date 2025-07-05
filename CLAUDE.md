# CLAUDE.md
# ───────────────────────────────────────────────
# AWS Lambda (AppSync GraphQL) 用 Claude ガイドライン
# ───────────────────────────────────────────────

## 応答のルール
- 常に日本語で応答してください。  
- コード部分はそのまま貼り付け、整形不要です。  
- ディスカッションや設計提案はマークダウンで記述してください。

## プロジェクト概要
- **ランタイム**: Python 3.9 (AWS Lambda)  
- **API**: AppSync GraphQL  
- **用途**: DynamoDB にゲームマッチ状態を保存／更新し、GraphQL でクライアントと同期  
- **ゴール**:  
  1. 全フェーズ（カード移動、ターン進行、攻撃宣言など）を Lambda で一貫処理  
  2. PassiveAura や Leader 能力などの常時効果をサーバ側で解決  
  3. 追加／削除されたステータスを events 経由でクライアントに通知  

## ディレクトリ規約
| フォルダ                       | 用途                                                    |
|-------------------------------|--------------------------------------------------------|
| `lambda_function.py`          | AppSync から呼び出されるエントリポイント              |
| `actions/`                    | 各種アクション（`PowerAura`、`Draw`、`BattleBuff` 等） |
| `action_registry.py`          | アクションタイプ → ハンドラのマッピング               |
| `helper.py`                   | 共通ユーティリティ／DynamoDB ラッパー                  |
| `schema.graphql`              | GraphQL スキーマ定義                                   |

## 基本作業方針

1. **PRD 受領 → Plan 化**  
   - PRD（この README や要件定義）を受け取ったら、疑問点を質問しクリアにする。  
   - `DocsForAI/Plan/` に「Lambda 実装 Plan.md」を作成。  
2. **ディレクトリ構造の確認**  
   - 上記規約に沿ってファイル配置を確認。  
3. **実装（Imp）**  
   - 触って良いファイルは `lambda_function.py`, `actions/`, `action_registry.py`, `helper.py` のみ。  
   - 1機能ずつコミット。コミットメッセージは `feat: moveCards resolver`, `refactor: passive auras cleanup` のように要約。  
4. **テスト**  
   - ローカル pytest で `moto` を使った DynamoDB モックを追加。  
   - `tests/` にユニットテストを作成。  
5. **デザイン出力**  
   - 実装後、`DocsForAI/Design/` に「Lambda 内部フロー.md」や「PassiveAura 処理設計.md」を保存。  
6. **レビュー & マージ**  
   - PR を立てたら、コードフローと主要処理にコメントを添えてください。  
   - 最終マージはユーザーが承認後に実施。  

---

**Issue 作成時にコメント例**  