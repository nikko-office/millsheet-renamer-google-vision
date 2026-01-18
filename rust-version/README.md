# ミルシートリネーマー (Rust版)

Google Cloud Vision API を使用して PDF ファイルからテキストを抽出し、ミルシート情報に基づいてファイル名を自動変更するツールのRust実装です。

## 機能

- ドラッグ＆ドロップ対応のGUIアプリ
- PDFの最初のページからテキストを抽出（Google Cloud Vision API）
- 日本語・英語テキストの認識に対応
- 抽出した情報からファイル名を自動生成
  - 発行日
  - 材質（SS400, SPHC, SUS304 など）
  - 寸法（厚さ x 幅 x 長さ）
  - メーカー名
  - 溶鋼番号/チャージ番号

## 必要条件

### システム要件

- Rust 1.70 以上
- Windows: Visual Studio Build Tools 2022（C++ワークロード）
- Poppler（PDF→画像変換用）

### Poppler のインストール

#### Windows

```powershell
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
2. プロジェクトを作成（または選択）
3. Cloud Vision API を有効化
4. サービスアカウントを作成し、JSONキーをダウンロード

### 2. ビルド

```bash
cd rust-version

# デバッグビルド
cargo build

# リリースビルド（最適化あり）
cargo build --release
```

### 3. 認証情報の配置

ダウンロードしたJSONキーファイルを以下のいずれかに配置:
- 環境変数 `GOOGLE_APPLICATION_CREDENTIALS` にパスを設定
- 実行ファイルと同じディレクトリに配置（自動検出）

## 使用方法

### GUIアプリ

```bash
# 開発時
cargo run

# リリースビルド後
./target/release/millsheet_renamer
```

1. アプリを起動
2. PDFファイルをウィンドウにドラッグ＆ドロップ
3. 自動的に処理され、元のファイルがリネームされます

## プロジェクト構成

```
rust-version/
├── Cargo.toml          # 依存関係・プロジェクト設定
├── README.md           # このファイル
└── src/
    ├── main.rs         # エントリポイント
    ├── lib.rs          # ライブラリルート
    ├── gui/            # GUIモジュール
    │   ├── mod.rs
    │   ├── app.rs      # メインアプリケーション
    │   └── theme.rs    # テーマ設定
    ├── vision/         # Vision APIモジュール
    │   ├── mod.rs
    │   ├── auth.rs     # 認証処理
    │   └── client.rs   # APIクライアント
    ├── pdf/            # PDF処理モジュール
    │   └── mod.rs      # pdftoppm呼び出し
    └── parser/         # テキスト解析モジュール
        ├── mod.rs
        ├── date.rs         # 日付抽出
        ├── material.rs     # 材質抽出
        ├── dimensions.rs   # 寸法抽出
        └── manufacturer.rs # メーカー名抽出
```

## 主な依存クレート

| クレート | 用途 |
|----------|------|
| eframe/egui | GUI フレームワーク |
| tokio | 非同期ランタイム |
| reqwest | HTTP クライアント |
| regex | 正規表現 |
| serde/serde_json | JSON シリアライズ |
| jsonwebtoken | JWT 生成（認証用） |
| base64 | Base64 エンコード |
| rfd | ファイルダイアログ |

## Python版との違い

- **パフォーマンス**: ネイティブコンパイルによる高速化
- **配布サイズ**: 単一の実行ファイル
- **GUI**: egui（Immediate Mode GUI）を使用
- **非同期処理**: tokio による効率的な並行処理

## ライセンス

MIT License
