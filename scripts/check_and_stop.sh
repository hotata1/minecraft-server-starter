#!/bin/bash

# スクリプト実行パスをサーバーディレクトリに設定
cd /home/ec2-user/minecraft/

# 必要な設定を環境変数から読み込む (GitHubにはダミーを記載)
# AWS CLIはEC2のIAMロールを使うため、アクセスキーは不要
# RCON_PASSはCron実行環境または.bashrcなどで定義することを推奨
RCON_PASS="${RCON_PASS:-DUMMY_RCON_PASSWORD}"
INSTANCE_ID="i-xxxxxxxxxxxxxxxxxx" # 停止対象のEC2インスタンスID

# mcrconがインストールされているか確認
if ! command -v mcrcon &> /dev/null
then
    echo "$(date): ERROR: mcrcon command not found. Aborting."
    exit 1
fi

# mcrconでプレイヤーリストを取得し、grepでプレイヤー数を示す行を抽出
# -P はPerl互換の正規表現、\K はマッチした文字列を結果に含めないことを意味する
PLAYER_COUNT=$(/usr/bin/mcrcon -H 127.0.0.1 -P 25575 -p "$RCON_PASS" "list" | grep -oP 'There are \K\d+')

# プレイヤー数が取得できなかった場合はエラーとみなし、処理を中断
if [ -z "$PLAYER_COUNT" ]; then
    echo "$(date): ERROR: Could not get player count (RCON connection failed?). Aborting."
    exit 1
fi

echo "$(date): Current players: $PLAYER_COUNT"

# プレイヤー数が0人か判定
if [ "$PLAYER_COUNT" -eq 0 ]; then
    
    echo "$(date): Player count is 0. Initiating shutdown..."

    # 1. サーバー内への警告メッセージ
    /usr/bin/mcrcon -H 127.0.0.1 -P 25575 -p "$RCON_PASS" "say 誰もいないため、30秒後にサーバーを安全に停止します。"

    # 2. サーバープロセスを安全に停止
    # Minecraftサーバーのプロセス停止には時間がかかるため、AWS CLI実行前に数秒待機を推奨
    /usr/bin/mcrcon -H 127.0.0.1 -P 25575 -p "$RCON_PASS" "stop"
    sleep 10 # サーバープロセスが終了するのを待つ

    # 3. EC2インスタンスを停止
    echo "$(date): Stopping EC2 instance $INSTANCE_ID."
    /usr/bin/aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region ap-northeast-1 

else
    echo "$(date): Players online. Skipping shutdown."
fi