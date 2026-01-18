//! 日付抽出モジュール

use regex::Regex;
use std::collections::HashMap;

/// テキストから発行日を抽出
/// 優先順位: 発行日ラベル付き > 英語月名形式 > 日本語形式 > 数字形式
pub fn extract_date(text: &str) -> Option<String> {
    // 優先度1: 発行日ラベル付きの日付
    if let Some(date) = extract_labeled_date(text) {
        return Some(date);
    }
    
    // 優先度2: 英語月名形式
    if let Some(date) = extract_english_date(text) {
        return Some(date);
    }
    
    // 優先度3: 日本語/数字形式
    extract_japanese_date(text)
}

/// 発行日ラベル付きの日付を抽出
fn extract_labeled_date(text: &str) -> Option<String> {
    let patterns = [
        r"発行日[\s\S]{0,50}?(\d{4}[./]\d{1,2}[./]\d{1,2})",
        r"Date\s*of\s*Issue[\s\S]{0,30}?(\d{4}[./]\d{1,2}[./]\d{1,2})",
        r"発行年月日[\s\S]{0,30}?(\d{4}[./]\d{1,2}[./]\d{1,2})",
    ];
    
    for pattern in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            if let Some(caps) = re.captures(text) {
                if let Some(m) = caps.get(1) {
                    if let Some(date) = parse_numeric_date(m.as_str()) {
                        return Some(date);
                    }
                }
            }
        }
    }
    
    None
}

/// 英語月名形式の日付を抽出
fn extract_english_date(text: &str) -> Option<String> {
    let month_map: HashMap<&str, u32> = [
        ("JAN", 1), ("JANUARY", 1),
        ("FEB", 2), ("FEBRUARY", 2),
        ("MAR", 3), ("MARCH", 3),
        ("APR", 4), ("APRIL", 4),
        ("MAY", 5),
        ("JUN", 6), ("JUNE", 6),
        ("JUL", 7), ("JULY", 7),
        ("AUG", 8), ("AUGUST", 8),
        ("SEP", 9), ("SEPTEMBER", 9),
        ("OCT", 10), ("OCTOBER", 10),
        ("NOV", 11), ("NOVEMBER", 11),
        ("DEC", 12), ("DECEMBER", 12),
    ].into_iter().collect();
    
    // AUG . 04 . 2025 or AUG.04.2025
    let patterns = [
        (r"([A-Z]{3,9})\s*[.\-/,]\s*(\d{1,2})\s*[.\-/,]\s*(\d{4})", "mdy"),
        (r"(\d{1,2})\s*[.\-/,]\s*([A-Z]{3,9})\s*[.\-/,]\s*(\d{4})", "dmy"),
        (r"(\d{4})\s*[.\-/,]\s*([A-Z]{3,9})\s*[.\-/,]\s*(\d{1,2})", "ymd"),
    ];
    
    for (pattern, format) in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            if let Some(caps) = re.captures(text) {
                let (year, month, day) = match format {
                    "mdy" => {
                        let month_str = caps.get(1)?.as_str().to_uppercase();
                        let month = *month_map.get(month_str.as_str())?;
                        let day: u32 = caps.get(2)?.as_str().parse().ok()?;
                        let year: u32 = caps.get(3)?.as_str().parse().ok()?;
                        (year, month, day)
                    }
                    "dmy" => {
                        let day: u32 = caps.get(1)?.as_str().parse().ok()?;
                        let month_str = caps.get(2)?.as_str().to_uppercase();
                        let month = *month_map.get(month_str.as_str())?;
                        let year: u32 = caps.get(3)?.as_str().parse().ok()?;
                        (year, month, day)
                    }
                    "ymd" => {
                        let year: u32 = caps.get(1)?.as_str().parse().ok()?;
                        let month_str = caps.get(2)?.as_str().to_uppercase();
                        let month = *month_map.get(month_str.as_str())?;
                        let day: u32 = caps.get(3)?.as_str().parse().ok()?;
                        (year, month, day)
                    }
                    _ => return None,
                };
                
                return Some(format!("{:02}-{:02}-{:02}", year % 100, month, day));
            }
        }
    }
    
    None
}

/// 日本語/数字形式の日付を抽出
fn extract_japanese_date(text: &str) -> Option<String> {
    let patterns: Vec<(&str, Option<&str>)> = vec![
        // 2024年1月15日
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", None),
        // 2024/01/15 or 2024/1/15
        (r"(\d{4})/(\d{1,2})/(\d{1,2})", None),
        // 2024-01-15
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", None),
        // 2024.01.15
        (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", None),
        // 令和6年1月15日
        (r"令和(\d{1,2})年(\d{1,2})月(\d{1,2})日", Some("reiwa")),
        // R6.1.15 or R06.01.15
        (r"R(\d{1,2})\.(\d{1,2})\.(\d{1,2})", Some("reiwa")),
        // 平成31年1月15日
        (r"平成(\d{1,2})年(\d{1,2})月(\d{1,2})日", Some("heisei")),
    ];
    
    for (pattern, era_type) in patterns {
        if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
            if let Some(caps) = re.captures(text) {
                let first: u32 = caps.get(1)?.as_str().parse().ok()?;
                let month: u32 = caps.get(2)?.as_str().parse().ok()?;
                let day: u32 = caps.get(3)?.as_str().parse().ok()?;
                
                let year = match era_type {
                    Some("reiwa") => 2018 + first,  // 令和1年 = 2019年
                    Some("heisei") => 1988 + first, // 平成1年 = 1989年
                    _ => first,
                };
                
                return Some(format!("{:02}-{:02}-{:02}", year % 100, month, day));
            }
        }
    }
    
    None
}

/// 数字形式の日付をパース (YYYY.MM.DD or YYYY/MM/DD or YYYY-MM-DD)
fn parse_numeric_date(date_str: &str) -> Option<String> {
    let re = Regex::new(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})").ok()?;
    let caps = re.captures(date_str)?;
    
    let year: u32 = caps.get(1)?.as_str().parse().ok()?;
    let month: u32 = caps.get(2)?.as_str().parse().ok()?;
    let day: u32 = caps.get(3)?.as_str().parse().ok()?;
    
    Some(format!("{:02}-{:02}-{:02}", year % 100, month, day))
}
