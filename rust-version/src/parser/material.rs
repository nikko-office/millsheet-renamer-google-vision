//! 材質抽出モジュール

use regex::Regex;

/// テキストから材質/鋼種を抽出
/// 対応: SS400, SPHC, SPCC, S45C, SUS304 など
pub fn extract_material(text: &str) -> Option<String> {
    let patterns = [
        // SS系 (一般構造用鋼)
        r"\b(SS\s*[234]\d{2})\b",
        // SPHC, SPCC, SPCD, SPCE (熱延/冷延鋼板)
        r"\b(SPH[CDE]|SPC[CDE])\b",
        // SECC, SECD (電気亜鉛めっき)
        r"\b(SEC[CD])\b",
        // SGCC, SGHC (溶融亜鉛めっき)
        r"\b(SG[CH]C)\b",
        // S-C系 (機械構造用炭素鋼)
        r"\b(S\d{2}C)\b",
        // SCM系 (クロムモリブデン鋼)
        r"\b(SCM\d{3})\b",
        // SUS系 (ステンレス鋼)
        r"\b(SUS\s*\d{3}[A-Z]?)\b",
        // SK系 (炭素工具鋼)
        r"\b(SK\d{1,2})\b",
        // SM系 (溶接構造用鋼)
        r"\b(SM\d{3}[A-C]?)\b",
        // STK系 (炭素鋼管)
        r"\b(STK\d{3})\b",
        // STKR系 (角形鋼管)
        r"\b(STKR\d{3})\b",
        // 汎用パターン
        r"\b(S[A-Z]{1,3}\d{2,3}[A-Z]?)\b",
    ];
    
    for pattern in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            if let Some(caps) = re.captures(text) {
                if let Some(m) = caps.get(1) {
                    let material = m.as_str().to_uppercase().replace(' ', "");
                    return Some(material);
                }
            }
        }
    }
    
    None
}
