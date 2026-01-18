//! ミルシートリネーマー - Google Cloud Vision API を使用したPDF自動リネームツール
//!
//! # 機能
//! - PDFファイルからGoogle Vision APIでテキスト抽出
//! - 日本語・英語テキストの認識
//! - 抽出情報（日付、材質、寸法、メーカー名）に基づく自動リネーム
//! - ドラッグ＆ドロップ対応GUI

pub mod gui;
pub mod parser;
pub mod pdf;
pub mod vision;

pub use parser::MillsheetInfo;
