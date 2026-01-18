//! テキスト解析モジュール - ミルシート情報の抽出

mod date;
mod dimensions;
mod manufacturer;
mod material;

use regex::Regex;

/// ミルシートから抽出された情報
#[derive(Debug, Clone, Default)]
pub struct MillsheetInfo {
    /// 発行日 (YY-MM-DD形式)
    pub date: Option<String>,
    /// 材質 (SS400, SPHC など)
    pub material: Option<String>,
    /// 寸法 (厚さx幅x長さ)
    pub dimensions: Option<String>,
    /// メーカー名
    pub manufacturer: Option<String>,
    /// 溶鋼番号/チャージ番号
    pub charge_no: Option<String>,
    /// 元のテキスト
    pub raw_text: String,
}

impl MillsheetInfo {
    /// テキストからミルシート情報を解析
    pub fn parse(text: &str) -> Self {
        Self {
            date: date::extract_date(text),
            material: material::extract_material(text),
            dimensions: dimensions::extract_dimensions(text),
            manufacturer: manufacturer::extract_manufacturer(text),
            charge_no: extract_charge_no(text),
            raw_text: text.to_string(),
        }
    }
    
    /// 新しいファイル名を生成
    /// フォーマット: [発行日]_[材質]_[寸法]_[メーカー名]_[Charge No].pdf
    pub fn generate_filename(&self, original_name: &str) -> String {
        let mut parts: Vec<String> = Vec::new();
        
        if let Some(ref date) = self.date {
            parts.push(date.clone());
        }
        
        if let Some(ref material) = self.material {
            parts.push(sanitize_for_filename(material));
        }
        
        if let Some(ref dimensions) = self.dimensions {
            parts.push(sanitize_for_filename(dimensions));
        }
        
        if let Some(ref manufacturer) = self.manufacturer {
            parts.push(sanitize_for_filename(manufacturer));
        }
        
        if let Some(ref charge_no) = self.charge_no {
            parts.push(sanitize_for_filename(charge_no));
        }
        
        if parts.is_empty() {
            // 情報が抽出できなかった場合は元のファイル名をベースにする
            let stem = std::path::Path::new(original_name)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("unknown");
            format!("{}_renamed.pdf", sanitize_for_filename(stem))
        } else {
            format!("{}.pdf", parts.join("_"))
        }
    }
}

/// 溶鋼番号/チャージ番号を抽出
fn extract_charge_no(text: &str) -> Option<String> {
    // ラベル付きパターン
    let labeled_patterns = [
        r"(?:溶[鋼銅]番号|CHARGE\s*N[oO]\.?|鋼番)\s*[:\s]*([A-Z0-9]{4,12})",
    ];
    
    for pattern in labeled_patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(text) {
                if let Some(m) = caps.get(1) {
                    let charge_no = m.as_str().to_uppercase();
                    if charge_no.len() >= 4 && charge_no.len() <= 12 && charge_no.chars().all(|c| c.is_alphanumeric()) {
                        return Some(charge_no);
                    }
                }
            }
        }
    }
    
    // 一般的なパターン
    let general_patterns = [
        r"\b([A-Z]{1,2}\d{4,8})\b",
        r"\b(\d{1,2}[A-Z]\d{4,6})\b",
    ];
    
    for pattern in general_patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(text) {
                if let Some(m) = caps.get(1) {
                    let charge_no = m.as_str().to_uppercase();
                    if charge_no.len() >= 4 && charge_no.len() <= 12 && charge_no.chars().all(|c| c.is_alphanumeric()) {
                        return Some(charge_no);
                    }
                }
            }
        }
    }
    
    None
}

/// ファイル名に使用できない文字を置換
fn sanitize_for_filename(text: &str) -> String {
    // 改行をスペースに置換
    let result = text.replace(['\r', '\n'], " ");
    
    // 無効な文字を置換
    let invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|'];
    let mut result: String = result
        .chars()
        .map(|c| if invalid_chars.contains(&c) { '_' } else { c })
        .collect();
    
    // 空白をアンダースコアに置換
    let whitespace_re = Regex::new(r"\s+").unwrap();
    result = whitespace_re.replace_all(&result, "_").to_string();
    
    // 連続するアンダースコアを1つに
    let underscore_re = Regex::new(r"_+").unwrap();
    result = underscore_re.replace_all(&result, "_").to_string();
    
    // 先頭と末尾のアンダースコアを削除
    result = result.trim_matches('_').to_string();
    
    // 最大50文字に制限
    if result.chars().count() > 50 {
        result = result.chars().take(50).collect();
    }
    
    result
}

/// ユニークなファイル名を取得（同名ファイルがある場合は連番を付与）
pub fn get_unique_filename(directory: &std::path::Path, filename: &str) -> String {
    let path = std::path::Path::new(filename);
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or(filename);
    let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("pdf");
    
    let mut final_name = filename.to_string();
    let mut counter = 1;
    
    while directory.join(&final_name).exists() {
        final_name = format!("{}_{}.{}", stem, counter, ext);
        counter += 1;
    }
    
    final_name
}
