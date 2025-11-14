# Minecraft Server Starter via LINE + AWS Lambda

このプロジェクトは、LINEメッセージをトリガーにしてAWS EC2上のMinecraftサーバーを起動し、LINEで通知するLambda関数のサンプルです。

## 🚀 機能概要

- LINEの「マイクラ起動」メッセージでEC2インスタンスを起動
- 起動後、IPアドレスをLINEで通知
- DynamoDBでユーザーIDを管理
- EC2の状態確認とポーリング処理（最大120秒）

## 🛠 必要な環境変数

`.env.example` を参考に `.env` ファイルを作成してください：

- `EC2_INSTANCE_ID`：起動対象のEC2インスタンスID
- `LINE_CHANNEL_ACCESS_TOKEN`：LINE Messaging APIのアクセストークン
- `DYNAMODB_TABLE_NAME`：ユーザーIDを保存するDynamoDBテーブル名

## 📦 デプロイ方法

1. 必要なライブラリを `requirements.txt` に記載（例：`boto3`）
2. Lambda関数と依存ライブラリをZIP化
3. AWS Lambdaにアップロードし、環境変数を設定
4. LINE DevelopersでWebhook URLをLambdaに設定

## ⚠️ 注意事項

- このコードはサンプルです。実運用にはIAM権限やセキュリティ設定を十分に確認してください。
- `.env` ファイルは絶対に公開しないでください。
- LINEユーザーIDやEC2のIPアドレスなどの個人情報はログや通知に含まれるため、公開時はマスクしてください。