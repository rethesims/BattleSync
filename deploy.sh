#!/usr/bin/env bash
set -euo pipefail

# 1. zip の出力先
ZIP_FILE=./syncbattle.zip

# 2. 既存の zip を削除
[ -f "$ZIP_FILE" ] && rm "$ZIP_FILE"

# 3. ディレクトリ丸ごと zip 化（必要なファイルだけ include すれば更に軽くできます）
zip -r "$ZIP_FILE" . -x 'deploy.sh'

# 4. AWS CLI で Lambda に直接デプロイ
aws lambda update-function-code \
  --function-name DCG_Sync_Battle \
  --zip-file "fileb://$ZIP_FILE"