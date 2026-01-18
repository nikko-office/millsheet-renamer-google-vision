//! PDF処理モジュール - PDFから画像への変換

use anyhow::{Context, Result};
use std::io::{Cursor, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

/// 埋め込みPoppler（zipファイル）
const EMBEDDED_POPPLER: &[u8] = include_bytes!("../poppler.zip");

/// 展開済みPopplerのパス（一度だけ展開）
static POPPLER_DIR: OnceLock<PathBuf> = OnceLock::new();

/// Popplerを一時フォルダに展開
fn extract_poppler() -> Result<PathBuf> {
    // 既に初期化済みならそのパスを返す
    if let Some(dir) = POPPLER_DIR.get() {
        return Ok(dir.clone());
    }
    
    let temp_dir = std::env::temp_dir().join("millsheet_poppler");
    
    // 既に展開済みならそのまま使う
    let pdftoppm_path = temp_dir.join("pdftoppm.exe");
    if pdftoppm_path.exists() {
        let _ = POPPLER_DIR.set(temp_dir.clone());
        return Ok(temp_dir);
    }
    
    // 展開
    std::fs::create_dir_all(&temp_dir)?;
    
    let cursor = Cursor::new(EMBEDDED_POPPLER);
    let mut archive = zip::ZipArchive::new(cursor)
        .context("埋め込みPopplerの読み込みに失敗")?;
    
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = temp_dir.join(file.name());
        
        if file.is_dir() {
            std::fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let mut outfile = std::fs::File::create(&outpath)?;
            let mut buffer = Vec::new();
            file.read_to_end(&mut buffer)?;
            outfile.write_all(&buffer)?;
        }
    }
    
    let _ = POPPLER_DIR.set(temp_dir.clone());
    Ok(temp_dir)
}

/// PDFの1ページ目を画像に変換
pub fn convert_pdf_to_image(pdf_path: impl AsRef<Path>) -> Result<PathBuf> {
    let pdf_path = pdf_path.as_ref();
    
    // 一時ディレクトリを作成
    let temp_dir = std::env::temp_dir().join(format!(
        "millsheet_{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis()
    ));
    std::fs::create_dir_all(&temp_dir)?;
    
    let output_base = temp_dir.join("page");
    
    // pdftoppmのパスを取得（埋め込みを展開）
    let poppler_dir = extract_poppler()?;
    let pdftoppm = poppler_dir.join("pdftoppm.exe");
    
    // pdftoppmコマンドを実行
    #[cfg(windows)]
    let output = Command::new(&pdftoppm)
        .args([
            "-png",
            "-f", "1",
            "-l", "1",
            "-r", "300",
        ])
        .arg(pdf_path)
        .arg(&output_base)
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .output()
        .with_context(|| format!("pdftoppmの実行に失敗: {:?}", pdftoppm))?;
    
    #[cfg(not(windows))]
    let output = Command::new(&pdftoppm)
        .args([
            "-png",
            "-f", "1",
            "-l", "1",
            "-r", "300",
        ])
        .arg(pdf_path)
        .arg(&output_base)
        .output()
        .with_context(|| format!("pdftoppmの実行に失敗: {:?}", pdftoppm))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("PDF変換に失敗: {}", stderr);
    }
    
    // 生成されたファイルを探す
    let image_path = temp_dir.join("page-1.png");
    if image_path.exists() {
        return Ok(image_path);
    }
    
    // page-01.png のパターンも試す
    let image_path = temp_dir.join("page-01.png");
    if image_path.exists() {
        return Ok(image_path);
    }
    
    anyhow::bail!("変換された画像ファイルが見つかりません")
}

/// 一時ファイルをクリーンアップ
pub fn cleanup_temp_image(image_path: impl AsRef<Path>) {
    let path = image_path.as_ref();
    if let Some(parent) = path.parent() {
        // 一時ディレクトリ全体を削除
        let _ = std::fs::remove_dir_all(parent);
    }
}

/// Popplerが利用可能かチェック（常にtrue、埋め込み済みのため）
pub fn is_poppler_available() -> bool {
    true
}

#[cfg(windows)]
trait CommandExt {
    fn creation_flags(&mut self, flags: u32) -> &mut Self;
}

#[cfg(windows)]
impl CommandExt for Command {
    fn creation_flags(&mut self, flags: u32) -> &mut Self {
        use std::os::windows::process::CommandExt as WinCommandExt;
        WinCommandExt::creation_flags(self, flags)
    }
}
