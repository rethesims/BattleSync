1. 概要
	•	実行環境: AWS Lambda（AppSync GraphQL リゾルバとして動作）
	•	目的: プレイヤー間のゲーム状態を DynamoDB テーブルに読み書きし、GraphQL API 経由で同期結果を返却する。

⸻

2. GraphQL スキーマ
	•	スキーマファイル: schema.graphql参照のこと
	•	主な Query / Mutation:

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


7. matchitemのサンプルは下記

{
  "pk": {
    "S": "183e8857-515a-4f78-b2bc-7eceed209dcf"
  },
  "sk": {
    "S": "STATE"
  },
  "battleReady": {
    "L": [
      {
        "S": "p1"
      },
      {
        "S": "p2"
      }
    ]
  },
  "battleStep": {
    "S": "Idle"
  },
  "cards": {
    "L": [
      {
        "M": {
          "baseCardId": {
            "S": "test_01"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "5"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "options": {
                            "L": [
                              {
                                "S": "yes"
                              },
                              {
                                "S": "no"
                              },
                              {
                                "S": "red"
                              },
                              {
                                "S": "blue"
                              },
                              {
                                "S": "green"
                              },
                              {
                                "S": "yellow"
                              },
                              {
                                "S": "black"
                              }
                            ]
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyLeader"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Draw"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnSummon"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "28f2e0c7-537a-4103-9bf3-2a5f8f6614d9"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "5"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Hand"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_01"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "5"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "options": {
                            "L": [
                              {
                                "S": "yes"
                              },
                              {
                                "S": "no"
                              },
                              {
                                "S": "red"
                              },
                              {
                                "S": "blue"
                              },
                              {
                                "S": "green"
                              },
                              {
                                "S": "yellow"
                              },
                              {
                                "S": "black"
                              }
                            ]
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyLeader"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Draw"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnSummon"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "66cd42de-5b11-44e5-bea8-878695dd3e43"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "5"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Field"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_01"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "5"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "options": {
                            "L": [
                              {
                                "S": "yes"
                              },
                              {
                                "S": "no"
                              },
                              {
                                "S": "red"
                              },
                              {
                                "S": "blue"
                              },
                              {
                                "S": "green"
                              },
                              {
                                "S": "yellow"
                              },
                              {
                                "S": "black"
                              }
                            ]
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyLeader"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Draw"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnSummon"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "11862a80-89cb-4ccc-b7b9-ad6d60f07c27"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "5"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Hand"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_18"
          },
          "currentDamage": {
            "N": "0"
          },
          "currentLevel": {
            "N": "3"
          },
          "currentPower": {
            "N": "0"
          },
          "damage": {
            "N": "0"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": "power<=3000"
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Destroy"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": "バトルに勝利した時、相手のパワー3000以下を1体破壊する"
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnBattleWin"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "ff6824a5-f243-4f02-8d22-cbb050dd2111"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "3"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "0"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_19"
          },
          "currentDamage": {
            "N": "0"
          },
          "currentLevel": {
            "N": "2"
          },
          "currentPower": {
            "N": "0"
          },
          "damage": {
            "N": "0"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "BlokedTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": "isProtect"
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "LoseProtect"
                          },
                          "mode": {
                            "S": ""
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "BlokedTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "BattleBuff"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": "攻撃時:相手のユニット1体はこのターン中プロテクトを失う。"
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnAttack"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "237800cc-467c-4c57-b167-8d3500af7f45"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "2"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "0"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_19"
          },
          "currentDamage": {
            "N": "0"
          },
          "currentLevel": {
            "N": "2"
          },
          "currentPower": {
            "N": "0"
          },
          "damage": {
            "N": "0"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "BlokedTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": "isProtect"
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "LoseProtect"
                          },
                          "mode": {
                            "S": ""
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "BlokedTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "BattleBuff"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": "攻撃時:相手のユニット1体はこのターン中プロテクトを失う。"
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnAttack"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "a97dd6c6-03f5-45be-ae43-705d15dda287"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "2"
          },
          "ownerId": {
            "S": "p1"
          },
          "power": {
            "N": "0"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_01"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "5"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "options": {
                            "L": [
                              {
                                "S": "yes"
                              },
                              {
                                "S": "no"
                              },
                              {
                                "S": "red"
                              },
                              {
                                "S": "blue"
                              },
                              {
                                "S": "green"
                              },
                              {
                                "S": "yellow"
                              },
                              {
                                "S": "black"
                              }
                            ]
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyLeader"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Draw"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnSummon"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "f840726c-7dd8-4a8e-9909-7a2f57da85df"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "5"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Hand"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_01"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "5"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "options": {
                            "L": [
                              {
                                "S": "yes"
                              },
                              {
                                "S": "no"
                              },
                              {
                                "S": "red"
                              },
                              {
                                "S": "blue"
                              },
                              {
                                "S": "green"
                              },
                              {
                                "S": "yellow"
                              },
                              {
                                "S": "black"
                              }
                            ]
                          },
                          "prompt": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyLeader"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Draw"
                          },
                          "value": {
                            "S": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnSummon"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "c9754faf-b713-4d1c-94cc-612573b6aa23"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "5"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_02"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "3"
          },
          "currentPower": {
            "N": "2000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "Gail"
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "PlayerField"
                          },
                          "targetFilter": {
                            "S": "isVanilla"
                          },
                          "type": {
                            "S": "KeywordAura"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "Passive"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "23fd23df-d184-4633-a801-794c0d7c542b"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "3"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "2000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_03"
          },
          "currentDamage": {
            "N": "2"
          },
          "currentLevel": {
            "N": "7"
          },
          "currentPower": {
            "N": "7000"
          },
          "damage": {
            "N": "2"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "aa"
                          },
                          "mode": {
                            "S": "aa"
                          },
                          "selectionKey": {
                            "S": "DeleteTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "N": "1"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": "UntilEndOfTurn"
                          },
                          "keyword": {
                            "S": "aa"
                          },
                          "mode": {
                            "S": "aa"
                          },
                          "selectionKey": {
                            "S": "DeleteTarget"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Destroy"
                          },
                          "value": {
                            "N": "1"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": "aa"
                  },
                  "description": {
                    "S": "出た時、相手の場のモンスターを1体選び破壊する。"
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "OnPlay"
                  }
                }
              },
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "Gail"
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "Self"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "KeywordAura"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "Passive"
                  }
                }
              },
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": "Critical"
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "Self"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "KeywordAura"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": false
                  },
                  "trigger": {
                    "S": "Passive"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "1a192705-375c-48c2-9834-c50fa0f3fa68"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "7"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "7000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_04"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "4"
          },
          "currentPower": {
            "N": "4000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "PayCost"
                          },
                          "value": {
                            "S": "2"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteKey"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteKey"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Destroy"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": true
                  },
                  "trigger": {
                    "S": "OnDestroy"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "14953e53-045e-4dd1-9f3e-76d97b16522e"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "4"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "4000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      },
      {
        "M": {
          "baseCardId": {
            "S": "test_04"
          },
          "currentDamage": {
            "N": "1"
          },
          "currentLevel": {
            "N": "4"
          },
          "currentPower": {
            "N": "4000"
          },
          "damage": {
            "N": "1"
          },
          "effectList": {
            "L": [
              {
                "M": {
                  "actions": {
                    "L": [
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": ""
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "PayCost"
                          },
                          "value": {
                            "S": "2"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteKey"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": "EnemyField"
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Select"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      },
                      {
                        "M": {
                          "duration": {
                            "S": ""
                          },
                          "keyword": {
                            "S": ""
                          },
                          "mode": {
                            "S": ""
                          },
                          "selectionKey": {
                            "S": "DeleteKey"
                          },
                          "sourceKey": {
                            "S": ""
                          },
                          "subValue": {
                            "N": "0"
                          },
                          "target": {
                            "S": ""
                          },
                          "targetFilter": {
                            "S": ""
                          },
                          "type": {
                            "S": "Destroy"
                          },
                          "value": {
                            "N": "0"
                          }
                        }
                      }
                    ]
                  },
                  "activationType": {
                    "S": ""
                  },
                  "condition": {
                    "S": ""
                  },
                  "description": {
                    "S": ""
                  },
                  "oncePerTurn": {
                    "BOOL": false
                  },
                  "optional": {
                    "BOOL": true
                  },
                  "trigger": {
                    "S": "OnDestroy"
                  }
                }
              }
            ]
          },
          "equippedTo": {
            "NULL": true
          },
          "id": {
            "S": "fb6f50cf-1657-44a7-a331-afdca072efb7"
          },
          "isFaceUp": {
            "BOOL": false
          },
          "level": {
            "N": "4"
          },
          "ownerId": {
            "S": "p2"
          },
          "power": {
            "N": "4000"
          },
          "statuses": {
            "L": []
          },
          "tempStatuses": {
            "L": []
          },
          "zone": {
            "S": "Deck"
          }
        }
      }
    ]
  },
  "choiceRequests": {
    "L": []
  },
  "choiceResponses": {
    "L": []
  },
  "createdAt": {
    "S": "2025-07-05T08:17:20.786+00:00"
  },
  "id": {
    "S": "183e8857-515a-4f78-b2bc-7eceed209dcf"
  },
  "levelPoints": {
    "L": [
      {
        "M": {
          "Color": {
            "N": "0"
          },
          "IsUsed": {
            "BOOL": false
          }
        }
      },
      {
        "M": {
          "Color": {
            "N": "0"
          },
          "IsUsed": {
            "BOOL": false
          }
        }
      }
    ]
  },
  "matchVersion": {
    "N": "9"
  },
  "pendingBattle": {
    "M": {
      "attackerId": {
        "NULL": true
      },
      "blockerId": {
        "NULL": true
      },
      "isLeader": {
        "BOOL": false
      },
      "targetId": {
        "NULL": true
      }
    }
  },
  "phase": {
    "S": "Main"
  },
  "playerDecks": {
    "L": [
      {
        "M": {
          "deckJson": {
            "S": "{\"cardIds\": [\"test_01\", \"test_01\", \"test_01\", \"test_18\", \"test_19\", \"test_19\"], \"deckName\": \"\\u30de\\u30a4\\u30c7\\u30c3\\u30ad\", \"leaderId\": 1}"
          },
          "playerId": {
            "S": "p1"
          }
        }
      },
      {
        "M": {
          "deckJson": {
            "S": "{\"deckName\": \"AI Starter\", \"leaderId\": 1, \"cardIds\": [\"test_01\", \"test_01\", \"test_02\", \"test_03\", \"test_04\", \"test_04\"]}"
          },
          "playerId": {
            "S": "p2"
          }
        }
      }
    ]
  },
  "players": {
    "L": [
      {
        "M": {
          "id": {
            "S": "p1"
          },
          "isReady": {
            "BOOL": true
          },
          "leaderId": {
            "S": "leader_001"
          },
          "name": {
            "S": "ap-northeast-1:e30582bd-f8c9-cc29-57b5-db2e9b5e577a"
          }
        }
      },
      {
        "M": {
          "id": {
            "S": "p2"
          },
          "isReady": {
            "BOOL": true
          },
          "leaderId": {
            "S": "leader_001"
          },
          "name": {
            "S": "AI_p2"
          }
        }
      }
    ]
  },
  "status": {
    "S": "BATTLE"
  },
  "turnCount": {
    "N": "0"
  },
  "turnPlayerId": {
    "S": "p1"
  },
  "updatedAt": {
    "S": "2025-07-05T08:17:55.506+00:00"
  }
}