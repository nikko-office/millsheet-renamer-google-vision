//! テーマ設定 - ダークテーマ

use egui::{Color32, Visuals, Style, CornerRadius, Stroke};

/// カラーパレット
pub struct Colors;

impl Colors {
    pub const BG_DARK: Color32 = Color32::from_rgb(10, 15, 26);
    pub const BG_CARD: Color32 = Color32::from_rgb(18, 26, 45);
    pub const BG_HOVER: Color32 = Color32::from_rgb(26, 37, 64);
    pub const ACCENT: Color32 = Color32::from_rgb(255, 107, 91);
    pub const ACCENT_HOVER: Color32 = Color32::from_rgb(255, 133, 119);
    pub const TEXT_PRIMARY: Color32 = Color32::from_rgb(255, 255, 255);
    pub const TEXT_SECONDARY: Color32 = Color32::from_rgb(139, 157, 195);
    pub const SUCCESS: Color32 = Color32::from_rgb(74, 222, 128);
    pub const ERROR: Color32 = Color32::from_rgb(248, 113, 113);
    pub const BORDER: Color32 = Color32::from_rgb(42, 58, 92);
}

/// ダークテーマのスタイルを作成
pub fn dark_theme() -> Style {
    let mut style = Style::default();
    
    // ビジュアル設定
    let mut visuals = Visuals::dark();
    
    visuals.panel_fill = Colors::BG_DARK;
    visuals.window_fill = Colors::BG_CARD;
    visuals.extreme_bg_color = Colors::BG_DARK;
    visuals.faint_bg_color = Colors::BG_CARD;
    
    // ウィジェットのスタイル
    visuals.widgets.noninteractive.bg_fill = Colors::BG_CARD;
    visuals.widgets.noninteractive.fg_stroke = Stroke::new(1.0, Colors::TEXT_SECONDARY);
    visuals.widgets.noninteractive.corner_radius = CornerRadius::same(8);
    
    visuals.widgets.inactive.bg_fill = Colors::BG_CARD;
    visuals.widgets.inactive.fg_stroke = Stroke::new(1.0, Colors::TEXT_PRIMARY);
    visuals.widgets.inactive.corner_radius = CornerRadius::same(8);
    
    visuals.widgets.hovered.bg_fill = Colors::BG_HOVER;
    visuals.widgets.hovered.fg_stroke = Stroke::new(1.0, Colors::TEXT_PRIMARY);
    visuals.widgets.hovered.corner_radius = CornerRadius::same(8);
    
    visuals.widgets.active.bg_fill = Colors::ACCENT;
    visuals.widgets.active.fg_stroke = Stroke::new(1.0, Colors::TEXT_PRIMARY);
    visuals.widgets.active.corner_radius = CornerRadius::same(8);
    
    visuals.selection.bg_fill = Colors::ACCENT.gamma_multiply(0.5);
    visuals.selection.stroke = Stroke::new(1.0, Colors::ACCENT);
    
    style.visuals = visuals;
    
    style
}
