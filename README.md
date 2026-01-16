# PDF テキスト抽出・ファイル名変更ツール

Google Cloud Vision API を使用して PDF ファイルから日本語テキストを抽出し、抽出したテキストに基づいてファイル名を自動的に変更するツールです。

## 機能

- PDF の最初のページからテキストを抽出
- 日本語・英語テキストの認識に対応
- 抽出したテキストからファイル名を自動生成
- ミルシート・検査証明書などの文書に最適化

## 必要条件

### システム要件

- Node.js 18 以上
- Poppler（PDF から画像への変換に使用）

### Poppler のインストール

#### Windows

```bash
# Chocolatey を使用する場合
choco install poppler

# または、手動でインストール
# https://github.com/oschwartz10612/poppler-windows/releases からダウンロード
# 解凍して、bin フォルダを PATH に追加
```

#### macOS

```bash
brew install poppler
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get install poppler-utils
```

## セットアップ

### 1. Google Cloud Platform の設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成（または既存のプロジェクトを選択）
3. Cloud Vision API を有効化:
   - 「APIとサービス」→「ライブラリ」
   - 「Cloud Vision API」を検索して有効化
4. サービスアカウントを作成:
   - 「IAMと管理」→「サービスアカウント」
   - 「サービスアカウントを作成」をクリック
   - 名前を入力（例: `vision-api-user`）
   - ロールは「Cloud Vision API ユーザー」を選択
5. JSON キーをダウンロード:
   - 作成したサービスアカウントをクリック
   - 「キー」タブ →「鍵を追加」→「新しい鍵を作成」
   - JSON 形式を選択してダウンロード

### 2. プロジェクトの設定

```bash
# 依存関係をインストール
npm install

# 環境変数ファイルを作成
cp .env.example .env

# .env ファイルを編集
# GOOGLE_APPLICATION_CREDENTIALS にダウンロードした JSON キーのパスを設定
```

### 3. 認証情報の配置

ダウンロードした JSON キーファイルをプロジェクトルートに配置し、`.env` ファイルでパスを指定:

```env
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

## 使用方法

### 基本的な使い方

1. `input` フォルダに処理したい PDF ファイルを配置
2. スクリプトを実行:

```bash
npm start
# または
node index.js
```

3. `output` フォルダに名前変更された PDF が出力されます

### ディレクトリ構成

```
project/
├── input/           # 処理前の PDF を配置
├── output/          # 名前変更後の PDF が出力される
├── index.js         # メインスクリプト
├── .env             # 環境変数（要作成）
└── service-account-key.json  # GCP 認証キー（要配置）
```

## 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP サービスアカウントキーのパス | `./service-account-key.json` |
| `PDF_INPUT_DIR` | 入力 PDF ディレクトリ | `./input` |
| `PDF_OUTPUT_DIR` | 出力 PDF ディレクトリ | `./output` |

## トラブルシューティング

### エラー: "pdftoppm: command not found"

Poppler がインストールされていないか、PATH に追加されていません。上記のインストール手順を確認してください。

### エラー: "Could not load the default credentials"

Google Cloud 認証情報が正しく設定されていません:
- `.env` ファイルが存在するか確認
- `GOOGLE_APPLICATION_CREDENTIALS` のパスが正しいか確認
- JSON キーファイルが存在するか確認

### エラー: "Cloud Vision API has not been enabled"

Google Cloud Console で Cloud Vision API を有効化してください。

### テキストが正しく抽出されない

- PDF の画質が低い場合、認識精度が下がることがあります
- スキャンした文書は 300 DPI 以上を推奨します

## 料金について

Google Cloud Vision API は従量課金制です:
- 最初の 1,000 ユニット/月は無料
- それ以降は 1,000 ユニットあたり $1.50

詳細は [Cloud Vision API の料金](https://cloud.google.com/vision/pricing) をご確認ください。

## ライセンス

MIT License
