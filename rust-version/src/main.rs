//! ミルシートリネーマー - メインエントリポイント

use anyhow::Result;

fn main() -> Result<()> {
    // ロギング初期化
    tracing_subscriber::fmt::init();

    // 環境変数の読み込み
    dotenvy::dotenv().ok();

    // GUIアプリケーション起動
    millsheet_renamer::gui::run()
}
