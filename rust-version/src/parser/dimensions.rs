//! 寸法抽出モジュール

use regex::Regex;

/// テキストから寸法を抽出
/// フォーマット: 厚さ x 幅 x 長さ/COIL
pub fn extract_dimensions(text: &str) -> Option<String> {
    // 寸法セクションを探す
    let dimension_section = find_dimension_section(text);
    
    let search_texts: Vec<&str> = if let Some(ref section) = dimension_section {
        vec![section.as_str(), text]
    } else {
        vec![text]
    };
    
    for search_text in search_texts {
        if let Some(dims) = try_extract_dimensions(search_text) {
            return Some(dims);
        }
    }
    
    // フォールバック: 厚さのみ抽出
    extract_thickness_only(text)
}

/// 寸法セクションを探す
fn find_dimension_section(text: &str) -> Option<String> {
    if let Ok(re) = Regex::new(r"(?i)(?:DIMENSIONS?|寸法)[^\n]*\n?([^\n]+)") {
        if let Some(caps) = re.captures(text) {
            let full = caps.get(0)?.as_str();
            let next_line = caps.get(1).map(|m| m.as_str()).unwrap_or("");
            return Some(format!("{}{}", full, next_line));
        }
    }
    None
}

/// 寸法の抽出を試みる
fn try_extract_dimensions(text: &str) -> Option<String> {
    // パターン定義 (具体的なものから汎用的なものへ)
    let patterns: Vec<(&str, usize)> = vec![
        // 22. 00X1, 540XCOIL (OCRで空白が入るパターン)
        (r"(\d{1,2})\.\s*(\d{2})\s*[xX×]\s*(\d)[,.]?\s*(\d{3})\s*[xX×]\s*(COIL|コイル|C)\b", 5),
        // 22.00X1.540XCOIL (小数点が幅に入るパターン)
        (r"(\d{1,2}\.?\d{0,2})[xX×](\d\.\d{3})[xX×](COIL|コイル|C)\b", 3),
        // 1.60X1,535XCOIL (カンマ区切り幅)
        (r"(\d+\.?\d*)\s*[xX×]\s*(\d{1,2},\d{3})\s*[xX×]\s*(COIL|コイル|C)\b", 3),
        // 1.6x1535xCOIL (標準パターン)
        (r"(\d+\.?\d*)\s*[xX×]\s*(\d{3,4})\s*[xX×]\s*(COIL|コイル|C)\b", 3),
        // 1.6X1219X2438 (数値長さ)
        (r"(\d+\.?\d*)\s*[xX×]\s*(\d{3,4})\s*[xX×]\s*(\d{3,4})", 3),
        // t1.6 x 1219 x COIL
        (r"t\s*(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*[xX×]\s*(COIL|コイル|C|\d+\.?\d*)", 3),
        // 板厚1.6 幅1219
        (r"板厚\s*(\d+\.?\d*)\s*.*?幅\s*(\d+\.?\d*)", 2),
        // 1.6t x 1219W
        (r"(\d+\.?\d*)\s*[tT]\s*[xX×]\s*(\d+\.?\d*)\s*[wW]?", 2),
    ];
    
    for (pattern, group_count) in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            for caps in re.captures_iter(text) {
                if let Some(dims) = parse_dimension_groups(&caps, group_count) {
                    return Some(dims);
                }
            }
        }
    }
    
    None
}

/// キャプチャグループから寸法を解析
fn parse_dimension_groups(caps: &regex::Captures, group_count: usize) -> Option<String> {
    match group_count {
        5 => {
            // "22. 00X1, 540XCOIL" パターン
            let thickness = format!("{}.{}", caps.get(1)?.as_str(), caps.get(2)?.as_str());
            let width = format!("{}{}", caps.get(3)?.as_str(), caps.get(4)?.as_str());
            let length = caps.get(5)?.as_str();
            
            if is_valid_dimension(&thickness, &width, Some(length)) {
                let t = format_thickness(&thickness);
                let l = normalize_length(length);
                return Some(format!("{}x{}x{}", t, width, l));
            }
        }
        3 => {
            let thickness = caps.get(1)?.as_str();
            let width_raw = caps.get(2)?.as_str();
            let length = caps.get(3)?.as_str();
            
            let width = process_width(width_raw);
            
            if is_valid_dimension(thickness, &width, Some(length)) {
                let t = format_thickness(thickness);
                let l = normalize_length(length);
                return Some(format!("{}x{}x{}", t, width, l));
            }
        }
        2 => {
            let thickness = caps.get(1)?.as_str();
            let width_raw = caps.get(2)?.as_str();
            
            let width = process_width(width_raw);
            
            if is_valid_dimension(thickness, &width, None) {
                let t = format_thickness(thickness);
                return Some(format!("{}x{}", t, width));
            }
        }
        _ => {}
    }
    
    None
}

/// 厚さのみを抽出（フォールバック）
fn extract_thickness_only(text: &str) -> Option<String> {
    let patterns = [
        r"(?:寸法|Size)[\s\S]{0,100}?(\d{1,2}\.\d{1,2})\s*[xX×]",
        r"(\d{1,2}\.\d{2})\s*[xX×]\s*\d",
    ];
    
    for pattern in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            if let Some(caps) = re.captures(text) {
                let thickness = caps.get(1)?.as_str();
                if let Ok(t) = thickness.parse::<f64>() {
                    if (0.1..=100.0).contains(&t) {
                        return Some(format_thickness(thickness));
                    }
                }
            }
        }
    }
    
    None
}

/// 幅の値を処理（カンマ除去、小数点誤認識の修正）
fn process_width(width_raw: &str) -> String {
    let mut width = width_raw.replace(',', "");
    
    // 1.540 のような誤認識を 1540 に修正
    if let Ok(re) = Regex::new(r"^\d{1,2}\.\d{3}$") {
        if re.is_match(&width) {
            width = width.replace('.', "");
        }
    }
    
    width
}

/// 寸法が妥当かチェック
fn is_valid_dimension(thickness: &str, width: &str, length: Option<&str>) -> bool {
    let t: f64 = match thickness.replace(',', "").parse() {
        Ok(v) => v,
        Err(_) => return false,
    };
    
    let w: f64 = match width.replace(',', "").parse() {
        Ok(v) => v,
        Err(_) => return false,
    };
    
    // 厚さは 0.1-100mm
    if !(0.1..=100.0).contains(&t) {
        return false;
    }
    
    // 幅は 100-5000mm
    if !(100.0..=5000.0).contains(&w) {
        return false;
    }
    
    // 幅は厚さより大きい
    if w <= t {
        return false;
    }
    
    // 長さのチェック
    if let Some(l) = length {
        let l_upper = l.to_uppercase();
        if !["COIL", "コイル", "C"].contains(&l_upper.as_str()) {
            if let Ok(length_val) = l.replace(',', "").parse::<f64>() {
                if length_val < 100.0 {
                    return false;
                }
            }
        }
    }
    
    true
}

/// 厚さをフォーマット（22.00 -> 22）
fn format_thickness(thickness: &str) -> String {
    if let Ok(t) = thickness.parse::<f64>() {
        if t == t.trunc() {
            return format!("{}", t as i32);
        }
        // 不要な末尾のゼロを削除
        let formatted = format!("{:.2}", t);
        formatted.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        thickness.to_string()
    }
}

/// 長さを正規化（COIL/コイル -> C）
fn normalize_length(length: &str) -> String {
    let upper = length.to_uppercase();
    if upper == "COIL" || length == "コイル" {
        "C".to_string()
    } else {
        length.to_string()
    }
}
