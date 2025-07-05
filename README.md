1. 概要
	•	実行環境: AWS Lambda（AppSync GraphQL リゾルバとして動作）
	•	目的: プレイヤー間のゲーム状態を DynamoDB テーブルに読み書きし、GraphQL API 経由で同期結果を返却する。

⸻

2. GraphQL スキーマ
	•	スキーマファイル: schema.graphql
	•	主な Query / Mutation:

scalar AWSDateTime

#########################################
#             GraphQL Schema            #
#   (Battle-step & attack authority)    #
#########################################
### --- Scalars ----------------------------------------------------
scalar AWSJSON

type AdvancePhasePayload {
	match: Match!
	events: [PhaseEvent!]!
}

### --- Misc -------------------------------------------------------
type BatchUpdateResult {
	success: Boolean!
	errorMessage: String
}

enum BattleStep {
	Idle
	BlockChoice
	AttackAbility
	Resolve
	CleanUp
}

enum BattleStepMutation {
	declareAttack
	answerBlock
	resolveBattle
}

### --- Card -------------------------------------------------------
type CardInstance {
	id: ID!
	baseCardId: String!
	zone: ZoneType!
	ownerId: ID!
	isFaceUp: Boolean!
	level: Int!
	power: Int!
	damage: Int!
	statuses: [CardStatus!]!
	tempStatuses: [CardStatusWithExpire!]!
	additionalEffects: [AWSJSON!]!
	equippedTo: ID
}

### --- Re-usable objects -----------------------------------------
type CardStatus {
	key: String!
	value: String!
}

input CardStatusInput {
	instanceId: ID!
	key: String!
	value: String!
}

type CardStatusWithExpire {
	key: String!
	value: String!
	expireTurn: Int!
}

input CardTempStatusInput {
	instanceId: ID!
	key: String!
	value: String!
	expireTurn: Int!
}

### --- Choice / ClientUpdate -------------------------------------
type ChoiceRequest {
	requestId: ID!
	playerId: ID!
	promptText: String!
	options: [String!]!
}

type ChoiceResponse {
	requestId: ID!
	playerId: ID!
	selectedValue: String!
}

type ClientUpdate {
	matchId: ID!
	clientId: ID!
	updateType: String!
	payload: AWSJSON!
	timestamp: AWSDateTime!
}

### --- Match ------------------------------------------------------
type Match {
	id: ID!
	turnCount: Int!
	matchVersion: Int!
	status: String!
	players: [Player!]!
	turnPlayerId: ID!
	phase: String!
	cards: [CardInstance!]!
	createdAt: AWSDateTime!
	updatedAt: AWSDateTime!
	playerDecks: [PlayerDeck!]!
	battleReady: [ID!]!
	choiceRequests: [ChoiceRequest!]!
	choiceResponses: [ChoiceResponse!]!
	# -------------- NEW --------------
	battleStep: BattleStep!
	# 現在のバトル進行段階
	pendingBattle: PendingBattle
}

type MatchWithEvents {
	match: Match!
	events: [TriggerEvent!]!
}

# future use
### --- Mutation ---------------------------------------------------
input MoveInput {
	cardId: ID!
	toZone: ZoneType!
}

### --- Battle-state objects --------------------------------------
type PendingBattle {
	attackerId: ID!
	targetId: ID
	# null ならリーダー
	blockerId: ID
	isLeader: Boolean!
}

type PhaseEvent {
	type: String!
	payload: AWSJSON
}

### --- Players & Decks -------------------------------------------
type Player {
	id: ID!
	name: String!
	isReady: Boolean!
	deckJson: String
}

type PlayerDeck {
	playerId: ID!
	deckJson: String!
}

type TriggerEvent {
	type: String!
	payload: AWSJSON
}

### --- Enums ------------------------------------------------------
enum ZoneType {
	Deck
	Hand
	Field
	Graveyard
	Exile
	Environment
	Damage
	Counter
}

type Mutation {
	# Match lifecycle
	startMatch(playerName: String!): Match
	setPlayerReady(matchId: ID!, playerId: ID!): Match
	startBattle(matchId: ID!, playerId: ID!): Match
	# Card manipulation
	moveCard(matchId: ID!, cardId: ID!, toZone: ZoneType!): MatchWithEvents!
	moveCards(matchId: ID!, moves: [MoveInput!]!): MatchWithEvents!
	summonCard(matchId: ID!, cardId: ID!): MatchWithEvents!
	spawnToken(
		matchId: ID!,
		cardId: String!,
		zone: ZoneType!,
		ownerId: ID!,
		isVanilla: Boolean
	): MatchWithEvents!
	equipCard(matchId: ID!, equipCardId: ID!, targetCardId: ID!): MatchWithEvents!
	unequipCard(matchId: ID!, equipCardId: ID!): MatchWithEvents!
	# Turn / phase
	endTurn(matchId: ID!, playerId: ID!): AdvancePhasePayload!
	advancePhase(matchId: ID!): AdvancePhasePayload!
	updatePhase(matchId: ID!, phase: String!): Match
	setTurnPlayer(matchId: ID!, playerId: ID!): Match
	# Status / effect updates
	updateCardStatus(
		matchId: ID!,
		cardId: ID!,
		key: String!,
		value: String!
	): Match
	updateCardStatuses(matchId: ID!, updates: [CardStatusInput!]!): BatchUpdateResult!
	addTempStatus(matchId: ID!, status: CardTempStatusInput!): Match
	clearTempStatus(matchId: ID!, instanceId: ID!, key: String!): Match
	addAdditionalEffect(matchId: ID!, instanceId: ID!, effect: AWSJSON!): Match
	removeAdditionalEffect(matchId: ID!, instanceId: ID!, effectSource: String!): Match
	updateLevelPoints(matchId: ID!, isPlayer: Boolean!, json: String!): Match!
	# Client push
	publishClientUpdate(
		matchId: ID!,
		clientId: ID!,
		updateType: String!,
		payload: AWSJSON!
	): ClientUpdate
	# Choice flow
	sendChoiceRequest(matchId: ID!, json: String!): Match
	submitChoiceResponse(matchId: ID!, json: String!): Match
	# -------- Battle authority mutations --------
	declareAttack(
		matchId: ID!,
		attackerId: ID!,
		targetId: ID,
		# null = leader
targetIsLeader: Boolean!
	): MatchWithEvents
	setBlocker(matchId: ID!, blockerId: ID): MatchWithEvents
	resolveBattle(matchId: ID!): MatchWithEvents!
	resolveAck(matchId: ID!, sequence: Int!): MatchWithEvents!
}

### --- Query ------------------------------------------------------
type Query {
	getMatch(id: ID!): Match
	listOpenMatches: [Match!]!
}


⸻

3. イベントペイロード（Lambda の event）
	•	AppSync から渡される event オブジェクトをパースし、actionType や arguments フィールドで処理を振り分ける。
	•	例:

{
  "field": "moveCards",
  "arguments": {
    "matchId": "...",
    "moves": [ { "cardId": "...", "toZone": "Hand" } ]
  },
  "identity": { /* クライアント情報 */ }
}



⸻

4. ディレクトリ構成

.
├── action_registry.py    # GraphQL 動作名 と actions モジュールのマッピング
├── actions/              # 各バトルアクション: aura, battle_buff, draw, move_zone...
├── helper.py             # 共通ユーティリティ（入力検証, DynamoDB ラッパー）
├── lambda_function.py    # AppSync ハンドラエントリポイント (handler)
└── schema.graphql        # GraphQL スキーマ定義


⸻

5. データストレージ(マッチ情報)
	•	DynamoDB テーブル名: dcg-match
	•	パーティションキー: pk (String)
	•	ソートキー: sk (String)


⸻

6. 実装ガイドライン
	1.	Lambda エントリポイント構成
	•	lambda_function.py の lambda_handler(event, context) を起点に、event.info.fieldName（AppSync の field）で呼び出すリゾルバ（Query/Mutation）を判定。
	•	ほとんどの処理は「①状態読込 → ②ビジネスロジック実行 → ③DynamoDB に更新 → ④結果返却」というフローに統一する。
	2.	マッチ状態のロードと永続化
	•	DynamoDB の dcg-match テーブルから pk=matchId, sk=STATE を取得し、JSON（内部的には Decimal）にデシリアライズ。
	•	更新後は必ず updatedAt、matchVersion をインクリメントしてから put_item で保存。
	•	失敗時は例外を投げて AppSync に 500 レスポンス。
	3.	アクション／エフェクトの構造と実行順序
	•	各カードに内包された effectList（OnPlay, OnSummon, Passive など）をトリガーイベントと紐づけ。
	•	イベントキュー方式で、発生したイベントを展開→再帰的に発動条件をスキャン→対応アクションを逐次適用。
	•	すべての mutate ハンドラの末尾で、クライアントに送る events: [TriggerEvent!] を積み上げる。
	4.	Action モジュール設計（actions/ ディレクトリ）
	•	@register("ActionType") デコレータで登録し、action_registry.get(type) でディスパッチ。
	•	各ハンドラは (card, act, item, ownerId) → [ { type:…, payload:… }, … ] の形で返却し、副作用的に item（ゲーム状態）を書き換える。
	•	新規アクションを追加する際は、まず register("NewType") + actions/new_type.py に実装。
	5.	パッシブ処理の一元化
	•	Passive Aura（Leader／カード常在効果）はサーバ側で解決し、クライアントは単に結果を受け取るのみ。
	•	refresh_passive_auras(item, events) を各フェーズチェンジやカード移動／召喚の後に必ず呼び出し、
	•	条件成立時は apply_passive_effect で付与、
	•	条件不成立時は clear_passive_from_targets で解除、
	•	これによりクライアントとマッチ状態を完全同期。
	6.	ターゲット解決
	•	resolve_targets(src, act, item) で act.target（Self, PlayerField, EnemyField…）を一元管理。
	•	今後、targetFilter（例: power<=3000）の解析ロジックをここに追加していく。
	7.	条件式評価
	•	evaluate_condition(cond, leader_card, item) で文字列ベースの簡易 DSL（例: PlayerTurnAndSelfFieldCount==1）を評価。
	•	複雑な条件が増えたらこのメソッドにパーサ／関数を追加。
	8.	ログとモニタリング
	•	各主要ステップ（trigger → condition 判定 → action 付与／解除 → DynamoDB read/write）に logger.info を挿入。
	•	CloudWatch Logs フィルターで [PassiveAura] や [Action] 等を設け、動作確認や障害解析を容易に。
	9.	エラーハンドリング
	•	入力不正・state 不整合は早期に raise Exception(...) で止め、AppSync 側で 400 系として返却。
	•	DynamoDB エラー・Lambda 呼び出しエラーはそのまま 500 系に。
	10.	テスト・CI
	•	テストは、Unityのエディタプレイから開発者が都度実施している。


7. AI 連携メモ

Issue 作成時に以下をコメントしてください:

@claude implement the BattleSyncHandler Lambda based on the specification in README.

	•	生成先ファイル: lambda_function.py および actions/ の新規ファイル
	•	ブランチ名例: claude/implement-battleSync
