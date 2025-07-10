#!/usr/bin/env bash
set -euo pipefail

ZIP_FILE=./syncbattle.zip
[ -f "$ZIP_FILE" ] && rm "$ZIP_FILE"

# ─── ここを修正 ───
# -j を外して、actions/ フォルダはそのままディレクトリ構造で追加
zip -r "$ZIP_FILE" \
  lambda_function.py \
  helper.py \
  action_registry.py \
  actions/

# Lambda にデプロイ
aws lambda update-function-code \
  --function-name DCG_Sync_Battle \
  --zip-file "fileb://$ZIP_FILE"