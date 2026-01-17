# PDF テキスト抽出・ファイル名変更ツール (Python版)

Google Cloud Vision API を使用して PDF ファイルから日本語テキストを抽出し、抽出したテキストに基づいてファイル名を自動的に変更するツールです。

## 機能

- **ドラッグ＆ドロップ対応のGUIアプリ** 📁
- PDF の最初のページからテキストを抽出
- 日本語・英語テキストの認識に対応
- 抽出したテキストからファイル名を自動生成
- ミルシート・検査証明書などの文書に最適化

![GUI Screenshot](https://via.placeholder.com/600x400?text=Millsheet+Renamer+GUI)

## 抽出される情報

| 情報 | 説明 |
|------|------|
| 日付 | 2024年1月15日、2024/01/15、令和6年1月15日 など |
| 会社名 | 株式会社〇〇、〇〇有限会社 など |
| 文書タイプ | ミルシート、検査証明書、納品書 など |

## 必要条件

### システム要件

- Python 3.10 以上
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
# 仮想環境を作成（推奨）
python -m venv venv

# 仮想環境を有効化
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Windows (コマンドプロンプト)
.\venv\Scripts\activate.bat
# macOS/Linux
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt

# 環境変数ファイルを作成
# .env ファイルを作成し、以下の内容を設定
```

### 3. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成:

```env
# Google Cloud Platform 認証情報
# サービスアカウントキーファイルのパスを指定
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json

# 入力ディレクトリ（PDFファイルを配置するフォルダ）
PDF_INPUT_DIR=./input

# 出力ディレクトリ（名前変更されたPDFが出力されるフォルダ）
PDF_OUTPUT_DIR=./output
```

### 4. 認証情報の配置

ダウンロードした JSON キーファイルをプロジェクトルートに配置し、`.env` ファイルでパスを指定してください。

## 使用方法

### GUIアプリ（推奨）

1. GUIアプリを起動:

```bash
python app.py
```

2. ウィンドウが開いたら、PDFファイルをドラッグ＆ドロップ
3. 自動的に処理され、結果が表示されます
4. 「出力フォルダを開く」ボタンでリネームされたファイルを確認

### コマンドライン版

1. `input` フォルダに処理したい PDF ファイルを配置
2. スクリプトを実行:

```bash
python main.py
```

3. `output` フォルダに名前変更された PDF が出力されます

### 出力例

```
════════════════════════════════════════════════════════════
  PDF テキスト抽出・ファイル名変更ツール
  Google Cloud Vision API を使用した日本語OCR
════════════════════════════════════════════════════════════

3 個のPDFファイルを処理します

処理中: sample_millsheet.pdf
  - Google Vision APIでテキスト抽出中...
  - 抽出テキストを解析中...
    日付: 2024-12-15
    会社名: 東京製鐵株式会社
    文書タイプ: ミルシート
  - 新しいファイル名: 2024-12-15_東京製鐵株式会社_ミルシート.pdf

════════════════════════════════════════════════════════════
  処理結果サマリー
════════════════════════════════════════════════════════════

合計: 3 | 成功: 3 | 失敗: 0

✓ 名前変更成功:
  sample_millsheet.pdf
    → 2024-12-15_東京製鐵株式会社_ミルシート.pdf
```

### ディレクトリ構成

```
project/
├── input/              # 処理前の PDF を配置（コマンドライン版用）
├── output/             # 名前変更後の PDF が出力される
├── app.py              # GUIアプリ（ドラッグ＆ドロップ対応）
├── main.py             # コマンドライン版スクリプト
├── requirements.txt    # Python 依存関係
├── .env                # 環境変数（要作成）
└── service-account-key.json  # GCP 認証キー（要配置）
```

## 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP サービスアカウントキーのパス | - |
| `PDF_INPUT_DIR` | 入力 PDF ディレクトリ | `./input` |
| `PDF_OUTPUT_DIR` | 出力 PDF ディレクトリ | `./output` |

## トラブルシューティング

### エラー: "pdftoppm: command not found" または "FileNotFoundError"

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

## EXEファイルの作成

### ビルド方法

```bash
# build.batを実行するだけでOK
.\build.bat
```

または手動で:

```bash
pip install pyinstaller
pyinstaller --noconfirm millsheet_renamer.spec
```

### 出力先

ビルドが完了すると、以下の場所にEXEファイルが作成されます:

```
dist/MillsheetRenamer/
├── MillsheetRenamer.exe   # 実行ファイル
├── ... (その他の依存ファイル)
```

### EXE版の使い方

1. `dist/MillsheetRenamer` フォルダを好きな場所にコピー
2. **Google Cloud の認証キー（JSONファイル）を同じフォルダに配置**
3. `MillsheetRenamer.exe` をダブルクリックで起動
4. PDFファイルをドラッグ＆ドロップ
5. `output` フォルダにリネームされたファイルが出力されます

### 配布時の構成

```
MillsheetRenamer/
├── MillsheetRenamer.exe        # 実行ファイル
├── your-credentials.json       # GCP認証キー（必須）
├── output/                     # 出力フォルダ（自動作成）
└── ... (その他の依存ファイル)
```

---

## Node.js 版からの移行

以前の Node.js 版 (`index.js`) から Python 版へ移行する場合:

1. 既存の `input`、`output` フォルダはそのまま使用可能
2. 同じ Google Cloud の認証キー（JSON）を使用可能
3. 環境変数の設定形式は同じ

## ライセンス

MIT License
