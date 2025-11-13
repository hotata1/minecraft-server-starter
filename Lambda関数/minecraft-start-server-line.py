# osモジュールをインポート（環境変数アクセス用）
import os
# jsonモジュールをインポート（LINEのWebhookパース用）
import json
# boto3モジュールをインポート（AWS SDK for Python）
import boto3
# loggingモジュールをインポート（ログ出力用）
import logging
# timeモジュールをインポート（EC2起動完了を待つポーリングのために必要です）
import time 
# urllib.requestモジュールをインポート（LINE Messaging APIへのHTTPリクエストのために必要です）
import urllib.request 

# ロガーを取得
logger = logging.getLogger()
# ロギングレベルをDEBUGに設定
logger.setLevel('DEBUG') 

# 環境変数に関するコメント
# 環境変数から操作対象のEC2インスタンスIDを取得
INSTANCE_ID = os.environ.get('EC2_INSTANCE_ID') 
# 環境変数からLINE API認証トークンを取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
# 環境変数からユーザーIDを保存するDynamoDBテーブル名を取得
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')

# DynamoDB関連関数ブロックのコメント
# --- DynamoDB関連関数 ---

# ユーザーIDをDynamoDBに保存する関数を定義
def save_user_id(user_id):
    """
    User IDをDynamoDBに保存し、通知リストに登録する。
    
    Args:
        user_id (str): LINEユーザーID。
    """
# DynamoDBのリソースクライアントを初期化
    dynamodb = boto3.resource('dynamodb')
# DynamoDBテーブルのオブジェクトを取得
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
# 例外処理の開始
    try:
# テーブルに新しいアイテムを挿入
        table.put_item(
            Item={
# プライマリキーとしてユーザーIDを設定
                'UserId': user_id, 
# 通知対象としてマーク
                'Status': 'active' 
            }
        )
# ログ出力
        logger.info(f"User ID {user_id} saved to DynamoDB.")
# エラー処理
    except Exception as e:
# エラーログ出力
        logger.error(f"Failed to save user ID to DynamoDB: {e}")

# DynamoDBから全ユーザーIDを取得する関数を定義
def get_all_user_ids():
    """
    DynamoDBから登録されている全User IDを取得する（通知対象リスト）。
    
    Returns:
        list: 登録されている全ユーザーIDのリスト。
    """
# DynamoDBのリソースクライアントを初期化
    dynamodb = boto3.resource('dynamodb')
# DynamoDBテーブルのオブジェクトを取得
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
# 例外処理の開始
    try:
# テーブル全体をスキャン
        response = table.scan(
# ProjectionExpressionでUserIdのみを取得し、I/Oを削減
            ProjectionExpression='UserId'
        )
# 取得したアイテムからUserIdだけをリストとして抽出して返す
        return [item['UserId'] for item in response['Items']]
# エラー処理
    except Exception as e:
# エラーログ出力
        logger.error(f"Failed to retrieve user IDs from DynamoDB: {e}")
# エラー時は空のリストを返す
        return []

# LINEメッセージ送信関数ブロックのコメント
# --- LINEメッセージ送信関数 ---

# LINEのPush APIを使ってメッセージを送信する関数を定義
def send_line_push_message(target_id, message):
    """
    LINEのPush APIを使ってメッセージを特定のユーザーへ送信する。
    """
# HTTPヘッダーを設定
    line_headers = {
# ボディがJSONであることを示す
        'Content-Type': 'application/json',
# 認証トークンを設定
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}' 
    }
# LINE APIに送信するJSONボディを定義
    line_body = {
# 送信先ユーザーID
        'to': target_id, 
# 送信メッセージの形式
        'messages': [{'type': 'text', 'text': message}] 
    }
    
# 例外処理の開始
    try:
# LINE Push Message APIのエンドポイントURL
        url = 'https://api.line.me/v2/bot/message/push'
# JSONボディを文字列化し、バイトデータにエンコード
        json_data = json.dumps(line_body).encode('utf-8')
        
# urllib.requestでHTTP POSTリクエストを作成
        req = urllib.request.Request(
            url,
            data=json_data,
            headers=line_headers,
# HTTPメソッドをPOSTに設定
            method='POST'
        )
        
# リクエストを送信し、応答を取得
        with urllib.request.urlopen(req) as response:
# ステータスコードが200（成功）以外の場合はエラーログ
            if response.getcode() != 200:
                 logger.error(f"LINE API responded with status code: {response.getcode()}")
# 成功の場合
            else:
                 logger.info(f"Push message sent to {target_id}. Status: {response.getcode()}")
            
# HTTPリクエスト中にエラーが発生した場合
    except Exception as e:
# エラーログ出力
        logger.error(f"Failed to send push message to {target_id}: {e}")

# EC2関連関数ブロックのコメント
# --- EC2関連関数 ---

# EC2インスタンスの状態とIPアドレスを取得する関数を定義
def get_instance_state_and_ip(ec2_client, instance_id):
    """
    EC2インスタンスの状態とパブリックIPアドレスを取得する。

    Returns:
        tuple: (状態名: str, パブリックIP: str or None)
    """
# 例外処理の開始
    try:
# EC2の情報を取得
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
# インスタンス情報が存在しない場合のチェック
        if not response['Reservations'] or not response['Reservations'][0]['Instances']:
            return None, None
            
# インスタンス情報を取り出し
        instance_info = response['Reservations'][0]['Instances'][0]
# 状態名 (running, stopped, pending, ...)を取得
        state = instance_info['State']['Name'] 
# IPアドレスを取得。存在しない場合はNone
        public_ip = instance_info.get('PublicIpAddress') 
# 状態とIPアドレスをタプルで返す
        return state, public_ip
        
# エラー処理
    except Exception as e:
# エラーログ出力
        logger.error(f"Error describing EC2 instance: {e}")
# エラー時はNoneを返す
        return None, None


# Lambdaハンドラーブロックのコメント
# --- Lambda Handler ---
# Lambdaのエントリーポイント関数を定義
def lambda_handler(event, context):
    """
    AWS Lambdaのエントリーポイント。LINE Webhookイベントを処理する。
    """
# メインロジック全体の例外処理の開始
    try:
# Boto3 EC2クライアントを初期化
        ec2 = boto3.client('ec2')
# 初期化成功ログ
        logger.debug("Boto3 EC2 client initialized successfully.")
        
# LINEイベントデータ（JSON文字列）をPythonオブジェクトにパース
        line_event_data = json.loads(event['body'])
# 有効なLINEイベントが含まれていない場合のチェック
        if 'events' not in line_event_data:
# 処理するイベントがなければ200 OKを返して終了
            return {'statusCode': 200, 'body': json.dumps('No events to process')}

# 複数のイベントがまとめて送られる可能性に対応するためループ
        for line_event in line_event_data['events']:
            
# 処理の起点となるユーザーIDを取得
            source_id = line_event['source']['userId'] 
            
# --- follow (友達追加) イベントの処理 ---
            if line_event['type'] == 'follow':
# データベースにIDを保存
                save_user_id(source_id) 
# 歓迎メッセージを送信
                send_line_push_message(source_id, "✨ マイクラサーバー通知Botへようこそ！\n\n「マイクラ起動」と話しかけてね！あなたのIDを通知リストに登録しました。")
# 次のイベントへ
                continue 
            
# --- join (グループ参加) イベントの処理 (今回はスキップ) ---
            if line_event['type'] == 'join':
# ログを記録
                logger.info(f"Bot joined. Source type: {line_event['source']['type']}")
# 次のイベントへ
                continue 
            
# メッセージイベントかつテキストメッセージのみを対象とする
            if line_event['type'] != 'message' or line_event['message']['type'] != 'text':
# スキップ
                continue

# 受信テキストメッセージを取得し、小文字に変換
            message_text = line_event['message']['text'].lower()
            
# --- 起動コマンドの処理 ---
# メッセージに特定のキーワードが含まれているかチェック
            if "マイクラ起動" in message_text or "サーバー起動" in message_text:
                
# EC2インスタンスの現在の状態を取得
                current_state, public_ip = get_instance_state_and_ip(ec2, INSTANCE_ID)
# 通知メッセージ変数を初期化
                notification_message = ""

                if current_state == 'running':
# 既に起動中の場合
                    address_info = f"アドレス:\n**{public_ip}**" if public_ip else "IPアドレスは現在取得中です。"
# 起動中であることを示すメッセージを作成
                    notification_message = f"✅ マイクラサーバーは既に起動中です。\n\n{address_info}"
                
                elif current_state == 'stopped':
# 停止中の場合、起動処理を開始
                    try:
# EC2インスタンスの起動をリクエスト
                        ec2.start_instances(InstanceIds=[INSTANCE_ID])
                        logger.info(f"EC2 instance {INSTANCE_ID} starting...")
                        
                        final_ip = None
                        
# ★★★ 同期ポーリングロジック（最大120秒待機） ★★★
# 6秒間隔で20回（合計120秒）、IPアドレスが取得できるまで待機
                        for i in range(20): 
# 6秒間待機
                            time.sleep(6) 
                            
# 最新の状態とIPを取得
                            current_state, temp_ip = get_instance_state_and_ip(ec2, INSTANCE_ID)
                            
# 状態がrunningになり、かつIPアドレスが取得できたら成功
                            if current_state == 'running' and temp_ip:
                                final_ip = temp_ip
# ポーリング終了
                                break 
                            
# pendingやrunning以外の予期せぬ状態になったらエラーとして終了
                            if current_state != 'pending' and current_state != 'running':
                                notification_message = f"🚨 サーバー起動中に予期せぬ状態 {current_state} になりました。AWSコンソールを確認してください。"
                                final_ip = None
# ポーリング終了
                                break

# 待機中のログを出力
                            logger.info(f"Waiting for IP. Current state: {current_state}. Attempt: {i+1}")
                        
# 待機ループ終了後の処理
                        if final_ip:
# 成功時の通知メッセージ (Java版/統合版情報を含む)
                            BEDROCK_PORT = "19132" # 統合版のデフォルトポート
                            
                            notification_message = (
                                f"🎉 **マイクラサーバーが起動しました！**\n\n"
                                f"**IPアドレス:**\n"
                                f"**{final_ip}**\n\n"
                                f"【接続情報】\n"
                                f"🌐 **Java版 (PC)**: \n"
                                f"  アドレス: {final_ip}\n\n"
                                f"📱 **統合版/Bedrock (Switch/スマホ)**: \n"
                                f"  アドレス: {final_ip}\n"
                                f"  ポート: **{BEDROCK_PORT}**\n\n"
                                f"Cronによる自動停止が有効です。"
                            )
                        elif not notification_message:
# タイムアウトなどでIPが取得できなかった場合
                            notification_message = "⚠️ サーバーは起動しましたが、IPアドレスの取得に時間がかかっています（タイムアウト）。数分後に再度お試しください。"

# EC2起動リクエストまたはポーリング中にエラーが発生した場合
                    except Exception as e:
                        logger.error(f"Error starting or polling EC2 instance: {e}")
                        notification_message = "🚨 サーバーの起動中にエラーが発生しました。AWSの設定とIAM権限を確認してください。"
                        
                else:
# pending, shutting-downなど、stopped/running以外の状態
                    notification_message = f"⚠️ サーバーは現在 {current_state} 状態です。しばらく待ってから再度お試しください。"

# サーバー起動または状態確認の結果を、登録されている全ユーザーに通知
                NOTIFICATION_TARGETS = get_all_user_ids()
                for target_id in NOTIFICATION_TARGETS:
                    send_line_push_message(target_id, notification_message)
                
# EC2操作が実行されたので、Lambda関数を終了
                return {'statusCode': 200, 'body': json.dumps('Server status processed and notified to all users.')}

# 起動コマンドがなかった場合は、何もせずに終了
        return {'statusCode': 200, 'body': json.dumps('No action taken')}
        
# 想定外の致命的なエラーが発生した場合の処理
    except Exception as general_e:
# エラー詳細（トレースバック含む）をログに出力
        logger.error(f"FATAL UNHANDLED ERROR: {general_e}", exc_info=True)
# LINE Webhookの要件に基づき、200 OKで応答
        return {'statusCode': 200, 'body': json.dumps('Error occurred but processed')}