//! メーカー名抽出モジュール

use regex::Regex;

/// 優先メーカーリスト
const PRIORITY_MANUFACTURERS: &[(&str, &[&str])] = &[
    ("東京製鉄", &["東京製鉄", "東京製鐵", "東京製鉄所", "東京製鐵所", "TOKYO STEEL", "TOKYOSTEEL"]),
    ("中山製鋼", &["中山製鋼", "中山製鉄", "中山製鋼所", "中山製鉄所", "NAKAYAMA STEEL", "NAKAYAMA"]),
    ("神戸製鋼", &["神戸製鋼", "神戸製鉄", "神戸製鋼所", "神戸製鉄所", "KOBE STEEL", "KOBELCO"]),
];

/// テキストからメーカー名を抽出
pub fn extract_manufacturer(text: &str) -> Option<String> {
    let text_upper = text.to_uppercase();
    
    // 優先メーカーを先にチェック
    for (display_name, variants) in PRIORITY_MANUFACTURERS {
        for variant in *variants {
            if text_upper.contains(&variant.to_uppercase()) {
                return Some(display_name.to_string());
            }
        }
    }
    
    // その他の会社名パターン
    let patterns = [
        r"([^\s\n]{2,15}(?:製鉄|製鋼|製鐵))",
        r"([^\s\n]{2,15}(?:株式会社|㈱))",
        r"(?:製造者|メーカー)[：:]\s*([^\n]+)",
    ];
    
    for pattern in patterns {
        if let Ok(re) = Regex::new(pattern) {
            if let Some(caps) = re.captures(text) {
                if let Some(m) = caps.get(1) {
                    let name = m.as_str().trim();
                    if name.chars().count() >= 2 && name.chars().count() <= 20 {
                        return Some(name.to_string());
                    }
                }
            }
        }
    }
    
    None
}
