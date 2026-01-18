//! メインアプリケーションウィンドウ

use crate::parser::{get_unique_filename, MillsheetInfo};
use crate::pdf::{cleanup_temp_image, convert_pdf_to_image};
use crate::vision::VisionClient;
use anyhow::Result;
use eframe::egui;
use egui::{CentralPanel, RichText, Vec2};
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::Arc;
use tokio::runtime::Runtime;

use super::theme::{dark_theme, Colors};

/// 処理結果
#[derive(Clone)]
pub struct ProcessResult {
    pub success: bool,
    pub original: String,
    pub new_name: Option<String>,
    pub error: Option<String>,
    pub parsed: Option<MillsheetInfo>,
}

/// アプリケーション状態
pub struct MillsheetRenamerApp {
    /// Vision APIクライアント
    vision_client: Option<Arc<VisionClient>>,
    /// Tokioランタイム
    runtime: Runtime,
    /// 処理結果
    results: Vec<ProcessResult>,
    /// 処理中かどうか
    is_processing: bool,
    /// 現在の処理ファイル
    current_file: Option<String>,
    /// 進捗
    progress: f32,
    /// ステータスメッセージ
    status: String,
    /// エラーメッセージ
    error: Option<String>,
    /// 最後に処理したフォルダ
    last_folder: Option<PathBuf>,
    /// 結果受信チャンネル
    result_rx: Receiver<ProcessResult>,
    /// 結果送信チャンネル
    result_tx: Sender<ProcessResult>,
}

impl Default for MillsheetRenamerApp {
    fn default() -> Self {
        let (result_tx, result_rx) = channel();
        
        // Vision クライアントの初期化（埋め込み認証情報を使用）
        let vision_client = VisionClient::new().ok().map(Arc::new);
        
        Self {
            vision_client,
            runtime: Runtime::new().expect("Tokioランタイムの作成に失敗"),
            results: Vec::new(),
            is_processing: false,
            current_file: None,
            progress: 0.0,
            status: "PDFファイルをドロップして開始".to_string(),
            error: None,
            last_folder: None,
            result_rx,
            result_tx,
        }
    }
}

impl MillsheetRenamerApp {
    /// ファイルを処理
    fn process_files(&mut self, files: Vec<PathBuf>) {
        let pdf_files: Vec<PathBuf> = files
            .into_iter()
            .filter(|p| p.extension().is_some_and(|e| e.eq_ignore_ascii_case("pdf")))
            .collect();
        
        if pdf_files.is_empty() {
            self.status = "PDFファイルが見つかりません".to_string();
            return;
        }
        
        // 最初のファイルのフォルダを記録
        if let Some(first) = pdf_files.first() {
            self.last_folder = first.parent().map(|p| p.to_path_buf());
        }
        
        self.results.clear();
        self.is_processing = true;
        self.progress = 0.0;
        self.status = format!("{} 個のファイルを処理中...", pdf_files.len());
        
        let vision_client = self.vision_client.clone();
        let result_tx = self.result_tx.clone();
        let total = pdf_files.len();
        
        // バックグラウンドで処理
        self.runtime.spawn(async move {
            for (i, pdf_path) in pdf_files.into_iter().enumerate() {
                let result = process_single_pdf(&pdf_path, vision_client.as_ref().map(|c| c.as_ref())).await;
                let _ = result_tx.send(result);
                
                // 進捗更新（次のファイルへの準備として）
                let _ = i;
                let _ = total;
            }
        });
    }
    
    /// 結果を受信
    fn receive_results(&mut self) {
        while let Ok(result) = self.result_rx.try_recv() {
            self.results.push(result);
            let done = self.results.len();
            let success_count = self.results.iter().filter(|r| r.success).count();
            let fail_count = done - success_count;
            
            self.progress = done as f32 / done.max(1) as f32;
            
            // すべて完了したら
            if !self.is_processing {
                continue;
            }
            
            self.status = format!("完了: {} 件成功, {} 件失敗", success_count, fail_count);
            
            // まだ処理中かどうかは結果の数では判断できないので
            // ここでは仮に is_processing をそのままにしておく
        }
        
        // 結果がある && 新しい結果がない場合は処理完了
        if !self.results.is_empty() && self.result_rx.try_recv().is_err() {
            self.is_processing = false;
        }
    }
}

impl eframe::App for MillsheetRenamerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // 結果を受信
        self.receive_results();
        
        // ドロップされたファイルを処理
        if !ctx.input(|i| i.raw.dropped_files.is_empty()) {
            let files: Vec<PathBuf> = ctx.input(|i| {
                i.raw.dropped_files
                    .iter()
                    .filter_map(|f| f.path.clone())
                    .collect()
            });
            
            if !files.is_empty() && !self.is_processing {
                self.process_files(files);
            }
        }
        
        // 処理中は再描画を要求
        if self.is_processing {
            ctx.request_repaint();
        }
        
        CentralPanel::default().show(ctx, |ui| {
            ui.spacing_mut().item_spacing = Vec2::new(8.0, 12.0);
            
            // ヘッダー
            ui.horizontal(|ui| {
                ui.heading(RichText::new("ミルシートリネーマー")
                    .size(28.0)
                    .color(Colors::TEXT_PRIMARY));
                
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui.add_enabled(
                        self.last_folder.is_some(),
                        egui::Button::new("📁 フォルダを開く")
                    ).clicked() {
                        if let Some(ref folder) = self.last_folder {
                            let _ = open::that(folder);
                        }
                    }
                });
            });
            
            ui.label(RichText::new("PDFをドロップ → 解析 → 元のファイルを自動リネーム")
                .size(14.0)
                .color(Colors::TEXT_SECONDARY));
            
            ui.add_space(10.0);
            
            // 警告メッセージ（Vision クライアントが初期化できなかった場合のみ）
            if self.vision_client.is_none() {
                ui.group(|ui| {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new("⚠").size(24.0).color(Colors::ERROR));
                        ui.label(RichText::new("Vision APIクライアントの初期化に失敗しました")
                            .color(Colors::ERROR));
                    });
                });
                ui.add_space(10.0);
            }
            
            // ドロップゾーン
            let is_hovering = !ui.ctx().input(|i| i.raw.hovered_files.is_empty());
            
            let frame_color = if is_hovering {
                Colors::ACCENT
            } else {
                Colors::BORDER
            };
            
            let bg_color = if is_hovering {
                Colors::BG_HOVER
            } else {
                Colors::BG_CARD
            };
            
            let drop_zone_response = egui::Frame::new()
                .fill(bg_color)
                .stroke(egui::Stroke::new(2.0, frame_color))
                .corner_radius(16.0)
                .inner_margin(40.0)
                .show(ui, |ui| {
                    ui.set_min_size(Vec2::new(ui.available_width(), 180.0));
                    ui.vertical_centered(|ui| {
                        let icon = if is_hovering { "📥" } else { "📄" };
                        ui.label(RichText::new(icon).size(64.0));
                        
                        ui.label(RichText::new("PDFファイルをここにドロップ")
                            .size(20.0)
                            .color(Colors::TEXT_PRIMARY));
                        
                        ui.label(RichText::new("または、クリックしてファイルを選択")
                            .size(14.0)
                            .color(Colors::TEXT_SECONDARY));
                        
                        ui.label(RichText::new("対応形式: PDF")
                            .size(12.0)
                            .color(Colors::TEXT_SECONDARY));
                    });
                });
            
            // クリックでファイル選択
            if drop_zone_response.response.clicked() && !self.is_processing {
                if let Some(files) = rfd::FileDialog::new()
                    .add_filter("PDF files", &["pdf"])
                    .pick_files()
                {
                    self.process_files(files);
                }
            }
            
            ui.add_space(10.0);
            
            // 処理中表示
            if self.is_processing {
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(RichText::new(&self.status).color(Colors::ACCENT));
                });
                
                ui.add(egui::ProgressBar::new(self.progress)
                    .fill(Colors::ACCENT));
            }
            
            ui.add_space(10.0);
            
            // 結果セクション
            ui.horizontal(|ui| {
                ui.label(RichText::new("処理結果")
                    .size(16.0)
                    .color(Colors::TEXT_PRIMARY));
                
                if !self.results.is_empty() {
                    let success_count = self.results.iter().filter(|r| r.success).count();
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(RichText::new(format!("{}/{} 件成功", success_count, self.results.len()))
                            .size(13.0)
                            .color(Colors::TEXT_SECONDARY));
                    });
                }
            });
            
            // スクロール可能な結果リスト
            egui::ScrollArea::vertical()
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    for result in &self.results {
                        ui.add_space(4.0);
                        
                        egui::Frame::new()
                            .fill(Colors::BG_CARD)
                            .corner_radius(12.0)
                            .inner_margin(12.0)
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    // ステータスアイコン
                                    let (icon, color) = if result.success {
                                        ("✓", Colors::SUCCESS)
                                    } else {
                                        ("✗", Colors::ERROR)
                                    };
                                    ui.label(RichText::new(icon).size(16.0).color(color));
                                    
                                    ui.vertical(|ui| {
                                        ui.label(RichText::new(&result.original)
                                            .size(13.0)
                                            .color(Colors::TEXT_SECONDARY));
                                        
                                        if result.success {
                                            if let Some(ref new_name) = result.new_name {
                                                ui.label(RichText::new(format!("→ {}", new_name))
                                                    .size(14.0)
                                                    .color(Colors::TEXT_PRIMARY));
                                            }
                                        } else if let Some(ref error) = result.error {
                                            ui.label(RichText::new(format!("エラー: {}", error))
                                                .size(13.0)
                                                .color(Colors::ERROR));
                                        }
                                    });
                                });
                            });
                    }
                });
            
            // ステータスバー
            ui.with_layout(egui::Layout::bottom_up(egui::Align::LEFT), |ui| {
                egui::Frame::new()
                    .fill(Colors::BG_CARD)
                    .inner_margin(egui::Margin::symmetric(20, 15))
                    .show(ui, |ui| {
                        ui.label(RichText::new(&self.status)
                            .size(13.0)
                            .color(Colors::TEXT_SECONDARY));
                    });
            });
        });
    }
}

/// 単一のPDFファイルを処理
async fn process_single_pdf(pdf_path: &PathBuf, vision_client: Option<&VisionClient>) -> ProcessResult {
    let original = pdf_path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown.pdf")
        .to_string();
    
    let Some(client) = vision_client else {
        return ProcessResult {
            success: false,
            original,
            new_name: None,
            error: Some("Vision APIクライアントが初期化されていません".to_string()),
            parsed: None,
        };
    };
    
    // PDFを画像に変換
    let image_path = match convert_pdf_to_image(pdf_path) {
        Ok(path) => path,
        Err(e) => {
            return ProcessResult {
                success: false,
                original,
                new_name: None,
                error: Some(format!("PDF変換エラー: {}", e)),
                parsed: None,
            };
        }
    };
    
    // テキスト抽出
    let text = match client.extract_text(&image_path).await {
        Ok(text) => {
            cleanup_temp_image(&image_path);
            text
        }
        Err(e) => {
            cleanup_temp_image(&image_path);
            return ProcessResult {
                success: false,
                original,
                new_name: None,
                error: Some(format!("テキスト抽出エラー: {}", e)),
                parsed: None,
            };
        }
    };
    
    if text.is_empty() {
        return ProcessResult {
            success: false,
            original,
            new_name: None,
            error: Some("テキストを抽出できませんでした".to_string()),
            parsed: None,
        };
    }
    
    // テキスト解析
    let info = MillsheetInfo::parse(&text);
    
    // ファイル名生成
    let new_filename = info.generate_filename(&original);
    
    // 元のファイルと同じディレクトリでユニークなファイル名を取得
    let original_dir = pdf_path.parent().unwrap_or(std::path::Path::new("."));
    let unique_filename = get_unique_filename(original_dir, &new_filename);
    
    // ファイルをリネーム
    let new_path = original_dir.join(&unique_filename);
    if let Err(e) = std::fs::rename(pdf_path, &new_path) {
        return ProcessResult {
            success: false,
            original,
            new_name: None,
            error: Some(format!("リネームエラー: {}", e)),
            parsed: Some(info),
        };
    }
    
    ProcessResult {
        success: true,
        original,
        new_name: Some(unique_filename),
        error: None,
        parsed: Some(info),
    }
}

/// アプリケーションを起動
pub fn run() -> Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([700.0, 650.0])
            .with_min_inner_size([600.0, 550.0])
            .with_title("ミルシートリネーマー")
            .with_drag_and_drop(true),
        ..Default::default()
    };
    
    eframe::run_native(
        "ミルシートリネーマー",
        options,
        Box::new(|cc| {
            // ダークテーマを設定
            cc.egui_ctx.set_style(dark_theme());
            
            // 日本語フォントを設定
            let mut fonts = egui::FontDefinitions::default();
            
            // システムの日本語フォントを追加
            #[cfg(windows)]
            {
                if let Ok(font_data) = std::fs::read("C:\\Windows\\Fonts\\YuGothM.ttc") {
                    fonts.font_data.insert(
                        "yu_gothic".to_owned(),
                        egui::FontData::from_owned(font_data).into(),
                    );
                    
                    fonts.families
                        .entry(egui::FontFamily::Proportional)
                        .or_default()
                        .insert(0, "yu_gothic".to_owned());
                    
                    fonts.families
                        .entry(egui::FontFamily::Monospace)
                        .or_default()
                        .push("yu_gothic".to_owned());
                }
            }
            
            cc.egui_ctx.set_fonts(fonts);
            
            Ok(Box::new(MillsheetRenamerApp::default()))
        }),
    )
    .map_err(|e| anyhow::anyhow!("アプリケーションエラー: {}", e))
}
