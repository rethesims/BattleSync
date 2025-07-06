#!/usr/bin/env python3
"""
安全なエラーハンドリングのテストファイル
"""
import json
import boto3
from moto import mock_dynamodb
from decimal import Decimal
from lambda_function import lambda_handler

@mock_dynamodb
def test_safe_error_handling():
    """安全なエラーハンドリングのテスト"""
    
    # DynamoDB テーブルのセットアップ
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='BattleSync',
        KeySchema=[
            {'AttributeName': 'pk', 'KeyType': 'HASH'},
            {'AttributeName': 'sk', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'pk', 'AttributeType': 'S'},
            {'AttributeName': 'sk', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # テスト用のマッチデータ
    test_match = {
        'pk': 'test-match-001',
        'sk': 'STATE',
        'cards': [
            {
                'id': 'card-001',
                'zone': 'Field',
                'ownerId': 'player-001',
                'name': 'Test Card',
                'power': Decimal('100'),
                'damage': Decimal('50')
            }
        ],
        'players': [
            {
                'id': 'player-001',
                'name': 'Player 1',
                'leaderId': 'leader-001'
            },
            {
                'id': 'player-002',
                'name': 'Player 2',
                'leaderId': 'leader-002'
            }
        ],
        'battleStep': 'BlockChoice',
        'pendingBattle': {
            'attackerId': 'card-001',
            'attackerOwnerId': 'player-001'
        },
        'turnPlayerId': 'player-001',
        'status': 'InProgress',
        'updatedAt': '2024-01-01T00:00:00Z'
    }
    
    table.put_item(Item=test_match)
    
    # テストケース 1: 無効な攻撃者ID
    context = {'field': 'declareAttack', 'args': {'attackerId': 'invalid-card'}}
    event = {'info': context, 'arguments': context['args']}
    
    result = lambda_handler(event, None)
    
    # エラーイベントが返されることを確認
    assert 'events' in result
    assert len(result['events']) == 1
    assert result['events'][0]['type'] == 'InvalidAttacker'
    assert 'message' in result['events'][0]['payload']
    print("✓ 無効な攻撃者ID テスト通過")
    
    # テストケース 2: 攻撃者IDが存在しない
    context = {'field': 'declareAttack', 'args': {}}
    event = {'info': context, 'arguments': context['args']}
    
    result = lambda_handler(event, None)
    
    # 空のイベントが返されることを確認
    assert 'events' in result
    assert len(result['events']) == 0
    print("✓ 攻撃者ID未指定 テスト通過")
    
    # テストケース 3: 無効なカードID (summonCard)
    context = {'field': 'summonCard', 'args': {'cardId': 'invalid-card'}}
    event = {'info': context, 'arguments': context['args']}
    
    result = lambda_handler(event, None)
    
    # エラーイベントが返されることを確認
    assert 'events' in result
    assert len(result['events']) == 1
    assert result['events'][0]['type'] == 'CardNotFound'
    assert 'message' in result['events'][0]['payload']
    print("✓ 無効なカードID テスト通過")
    
    # テストケース 4: マッチIDが存在しない
    context = {'field': 'getMatch', 'args': {}}
    event = {'info': context, 'arguments': context['args']}
    
    result = lambda_handler(event, None)
    
    # エラーイベントが返されることを確認
    assert 'events' in result
    assert len(result['events']) == 1
    assert result['events'][0]['type'] == 'MissingMatchId'
    assert 'message' in result['events'][0]['payload']
    print("✓ マッチID未指定 テスト通過")
    
    # テストケース 5: サポートされていないフィールド
    context = {'field': 'unsupportedField', 'args': {'matchId': 'test-match-001'}}
    event = {'info': context, 'arguments': context['args']}
    
    result = lambda_handler(event, None)
    
    # エラーイベントが返されることを確認
    assert 'events' in result
    assert len(result['events']) == 1
    assert result['events'][0]['type'] == 'UnsupportedField'
    assert 'message' in result['events'][0]['payload']
    print("✓ サポート外フィールド テスト通過")
    
    print("\n🎉 すべてのテストが通過しました！")


if __name__ == '__main__':
    test_safe_error_handling()