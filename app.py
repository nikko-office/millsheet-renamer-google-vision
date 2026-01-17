#!/usr/bin/env python3
"""
PDF Text Extraction and File Renaming Tool - GUI Application
Drag and drop interface for processing PDF files with Google Cloud Vision API
"""

import os
import threading
from pathlib import Path
from typing import Callable
import subprocess
import sys
import shutil
import traceback

# Handle PyInstaller frozen executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APP_DIR = Path(sys.executable).parent
else:
    # Running as script
    APP_DIR = Path(__file__).parent

# Set up environment for exe
os.chdir(APP_DIR)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(APP_DIR / '.env')

# Auto-detect credentials file if not set
CREDENTIALS_FOUND = False
if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
    for cred_file in APP_DIR.glob('*.json'):
        if cred_file.name != 'package.json':
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(cred_file)
            CREDENTIALS_FOUND = True
            break
else:
    CREDENTIALS_FOUND = True

# Check if Poppler (pdftoppm) is available
def check_poppler():
    """Check if pdftoppm is available (bundled or system)"""
    # Check bundled poppler first
    poppler_paths = [
        APP_DIR / "poppler" / "bin" / "pdftoppm.exe",
        APP_DIR / "poppler" / "pdftoppm.exe",
        APP_DIR / "poppler-24.08.0" / "Library" / "bin" / "pdftoppm.exe",
        APP_DIR / "bin" / "pdftoppm.exe",
    ]
    
    for poppler_path in poppler_paths:
        if poppler_path.exists():
            return True
    
    # Check system PATH
    try:
        result = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

POPPLER_AVAILABLE = check_poppler()

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from main import (
    extract_text_from_pdf,
    parse_extracted_text,
    generate_new_filename,
    get_unique_filename,
    get_vision_client,
)

# ============================================================================
# Theme Configuration
# ============================================================================

# Color palette - Deep navy with coral accent
COLORS = {
    "bg_dark": "#0a0f1a",
    "bg_card": "#121a2d",
    "bg_hover": "#1a2540",
    "accent": "#ff6b5b",
    "accent_hover": "#ff8577",
    "text_primary": "#ffffff",
    "text_secondary": "#8b9dc3",
    "success": "#4ade80",
    "error": "#f87171",
    "border": "#2a3a5c",
}

ctk.set_appearance_mode("dark")


# ============================================================================
# Custom TkinterDnD + CustomTkinter Integration
# ============================================================================

class CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    """CustomTkinter window with drag and drop support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


# ============================================================================
# Drop Zone Widget
# ============================================================================

class DropZone(ctk.CTkFrame):
    """Drag and drop zone for PDF files"""
    
    def __init__(self, master, on_drop: Callable[[list[str]], None], **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=2,
            corner_radius=16,
            **kwargs
        )
        
        self.on_drop = on_drop
        self.is_hovering = False
        
        # Inner container
        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.pack(expand=True, fill="both", padx=40, pady=40)
        
        # Icon (using text as fallback)
        self.icon_label = ctk.CTkLabel(
            self.inner,
            text="📄",
            font=ctk.CTkFont(size=64),
            text_color=COLORS["text_secondary"]
        )
        self.icon_label.pack(pady=(20, 10))
        
        # Main text
        self.title_label = ctk.CTkLabel(
            self.inner,
            text="PDFファイルをここにドロップ",
            font=ctk.CTkFont(family="Yu Gothic UI", size=20, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(10, 5))
        
        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.inner,
            text="または、クリックしてファイルを選択",
            font=ctk.CTkFont(family="Yu Gothic UI", size=14),
            text_color=COLORS["text_secondary"]
        )
        self.subtitle_label.pack(pady=(0, 10))
        
        # Supported formats
        self.format_label = ctk.CTkLabel(
            self.inner,
            text="対応形式: PDF",
            font=ctk.CTkFont(family="Yu Gothic UI", size=12),
            text_color=COLORS["text_secondary"]
        )
        self.format_label.pack(pady=(10, 20))
        
        # Bind click to open file dialog
        self.bind("<Button-1>", self._on_click)
        self.inner.bind("<Button-1>", self._on_click)
        for child in self.inner.winfo_children():
            child.bind("<Button-1>", self._on_click)
        
        # Setup drag and drop
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<DropEnter>>", self._on_drag_enter)
        self.dnd_bind("<<DropLeave>>", self._on_drag_leave)
        self.dnd_bind("<<Drop>>", self._on_drop)
    
    def _on_click(self, event):
        """Open file dialog on click"""
        files = ctk.filedialog.askopenfilenames(
            title="PDFファイルを選択",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if files:
            self.on_drop(list(files))
    
    def _on_drag_enter(self, event):
        """Highlight drop zone on drag enter"""
        self.is_hovering = True
        self.configure(
            border_color=COLORS["accent"],
            fg_color=COLORS["bg_hover"]
        )
        self.icon_label.configure(text="📥")
        return event.action
    
    def _on_drag_leave(self, event):
        """Remove highlight on drag leave"""
        self.is_hovering = False
        self.configure(
            border_color=COLORS["border"],
            fg_color=COLORS["bg_card"]
        )
        self.icon_label.configure(text="📄")
        return event.action
    
    def _on_drop(self, event):
        """Handle dropped files"""
        self._on_drag_leave(event)
        
        # Parse dropped file paths
        data = event.data
        # Handle Windows paths with spaces (wrapped in braces)
        if "{" in data:
            import re
            files = re.findall(r'\{([^}]+)\}', data)
            # Also get paths without braces
            remaining = re.sub(r'\{[^}]+\}', '', data).strip()
            if remaining:
                files.extend(remaining.split())
        else:
            files = data.split()
        
        # Filter PDF files
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        
        if pdf_files:
            self.on_drop(pdf_files)
        
        return event.action


# ============================================================================
# Result Item Widget
# ============================================================================

class ResultItem(ctk.CTkFrame):
    """Single result item display"""
    
    def __init__(self, master, result: dict, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            **kwargs
        )
        
        self.result = result
        
        # Status indicator
        status_color = COLORS["success"] if result["success"] else COLORS["error"]
        status_text = "✓" if result["success"] else "✗"
        
        self.status_label = ctk.CTkLabel(
            self,
            text=status_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=status_color,
            width=30
        )
        self.status_label.pack(side="left", padx=(15, 5), pady=15)
        
        # File info container
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Original filename
        self.original_label = ctk.CTkLabel(
            info_frame,
            text=result["original"],
            font=ctk.CTkFont(family="Yu Gothic UI", size=13),
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        self.original_label.pack(fill="x")
        
        if result["success"]:
            # Arrow and new filename
            self.new_label = ctk.CTkLabel(
                info_frame,
                text=f"→ {result['new_name']}",
                font=ctk.CTkFont(family="Yu Gothic UI", size=14, weight="bold"),
                text_color=COLORS["text_primary"],
                anchor="w"
            )
            self.new_label.pack(fill="x", pady=(2, 0))
        else:
            # Error message
            self.error_label = ctk.CTkLabel(
                info_frame,
                text=f"エラー: {result['error']}",
                font=ctk.CTkFont(family="Yu Gothic UI", size=13),
                text_color=COLORS["error"],
                anchor="w"
            )
            self.error_label.pack(fill="x", pady=(2, 0))


# ============================================================================
# Main Application
# ============================================================================

class MillsheetRenamerApp(CTkDnD):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("ミルシートリネーマー")
        self.geometry("700x650")
        self.minsize(600, 550)
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Initialize Vision API client (lazy)
        self._vision_client = None
        
        # Store last processed folder for "open folder" button
        self._last_processed_folder = None
        
        # Build UI
        self._build_ui()
    
    @property
    def vision_client(self):
        """Lazy initialization of Vision API client"""
        if self._vision_client is None:
            self._vision_client = get_vision_client()
        return self._vision_client
    
    def _build_ui(self):
        """Build the user interface"""
        
        # Check for missing requirements and show warnings
        warnings = []
        if not POPPLER_AVAILABLE:
            warnings.append("⚠️ Poppler (pdftoppm) が見つかりません\n   → PDFの変換ができません\n   → Popplerをインストールしてください")
        if not CREDENTIALS_FOUND:
            warnings.append("⚠️ Google Cloud 認証キー (.json) が見つかりません\n   → EXEと同じフォルダに配置してください")
        
        if warnings:
            self._show_setup_warning(warnings)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(25, 15))
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="ミルシートリネーマー",
            font=ctk.CTkFont(family="Yu Gothic UI", size=28, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        title_label.pack(side="left")
        
        # Open folder button
        self.output_btn = ctk.CTkButton(
            header_frame,
            text="📁 フォルダを開く",
            font=ctk.CTkFont(family="Yu Gothic UI", size=13),
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=36,
            command=self._open_last_folder,
            state="disabled"
        )
        self.output_btn.pack(side="right")
        
        # Subtitle
        subtitle_label = ctk.CTkLabel(
            self,
            text="PDFをドロップ → 解析 → 元のファイルを自動リネーム",
            font=ctk.CTkFont(family="Yu Gothic UI", size=14),
            text_color=COLORS["text_secondary"]
        )
        subtitle_label.pack(anchor="w", padx=30, pady=(0, 20))
        
        # Drop zone
        self.drop_zone = DropZone(
            self,
            on_drop=self._on_files_dropped,
            height=200
        )
        self.drop_zone.pack(fill="x", padx=30, pady=(0, 20))
        
        # Results section
        results_header = ctk.CTkFrame(self, fg_color="transparent")
        results_header.pack(fill="x", padx=30, pady=(10, 5))
        
        results_title = ctk.CTkLabel(
            results_header,
            text="処理結果",
            font=ctk.CTkFont(family="Yu Gothic UI", size=16, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        results_title.pack(side="left")
        
        self.stats_label = ctk.CTkLabel(
            results_header,
            text="",
            font=ctk.CTkFont(family="Yu Gothic UI", size=13),
            text_color=COLORS["text_secondary"]
        )
        self.stats_label.pack(side="right")
        
        # Scrollable results area
        self.results_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.results_scroll.pack(fill="both", expand=True, padx=30, pady=(5, 20))
        
        # Status bar
        self.status_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=50, corner_radius=0)
        self.status_frame.pack(fill="x", side="bottom")
        self.status_frame.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="PDFファイルをドロップして開始",
            font=ctk.CTkFont(family="Yu Gothic UI", size=13),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(side="left", padx=20, pady=15)
        
        # Progress bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(
            self.status_frame,
            fg_color=COLORS["bg_hover"],
            progress_color=COLORS["accent"],
            height=4,
            corner_radius=2
        )
        self.progress_bar.set(0)
    
    def _show_setup_warning(self, warnings: list[str]):
        """Show setup warning dialog"""
        warning_text = "\n\n".join(warnings)
        
        # Create warning window
        warning_window = ctk.CTkToplevel(self)
        warning_window.title("セットアップ確認")
        warning_window.geometry("500x300")
        warning_window.configure(fg_color=COLORS["bg_dark"])
        warning_window.transient(self)
        warning_window.grab_set()
        
        # Center the window
        warning_window.update_idletasks()
        x = (warning_window.winfo_screenwidth() - 500) // 2
        y = (warning_window.winfo_screenheight() - 300) // 2
        warning_window.geometry(f"500x300+{x}+{y}")
        
        # Warning icon
        icon_label = ctk.CTkLabel(
            warning_window,
            text="⚠️",
            font=ctk.CTkFont(size=48),
            text_color=COLORS["error"]
        )
        icon_label.pack(pady=(20, 10))
        
        # Warning title
        title_label = ctk.CTkLabel(
            warning_window,
            text="必要な設定が見つかりません",
            font=ctk.CTkFont(family="Yu Gothic UI", size=18, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        title_label.pack(pady=(0, 15))
        
        # Warning message
        msg_label = ctk.CTkLabel(
            warning_window,
            text=warning_text,
            font=ctk.CTkFont(family="Yu Gothic UI", size=13),
            text_color=COLORS["text_secondary"],
            justify="left"
        )
        msg_label.pack(pady=(0, 20), padx=30)
        
        # OK button
        ok_btn = ctk.CTkButton(
            warning_window,
            text="OK",
            font=ctk.CTkFont(family="Yu Gothic UI", size=14),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            width=100,
            command=warning_window.destroy
        )
        ok_btn.pack(pady=(10, 20))
    
    def _open_last_folder(self):
        """Open the last processed folder in file explorer"""
        if self._last_processed_folder and self._last_processed_folder.exists():
            folder_path = self._last_processed_folder.resolve()
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
    
    def _on_files_dropped(self, files: list[str]):
        """Handle dropped files"""
        pdf_files = [Path(f) for f in files if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            self._set_status("PDFファイルが見つかりません", error=True)
            return
        
        # Process in background thread
        threading.Thread(target=self._process_files, args=(pdf_files,), daemon=True).start()
    
    def _process_files(self, pdf_files: list[Path]):
        """Process PDF files (runs in background thread)"""
        self._set_status(f"{len(pdf_files)} 個のファイルを処理中...", show_progress=True)
        self._clear_results()
        
        results = []
        total = len(pdf_files)
        
        # Store the folder of the first file
        if pdf_files:
            self._last_processed_folder = pdf_files[0].parent
        
        for i, pdf_path in enumerate(pdf_files):
            # Update progress
            progress = (i + 1) / total
            self.after(0, lambda p=progress, f=pdf_path.name: self._update_progress(p, f"処理中: {f}"))
            
            # Process file
            result = self._process_single_pdf(pdf_path)
            results.append(result)
            
            # Add result to UI
            self.after(0, lambda r=result: self._add_result(r))
        
        # Final status
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        status_text = f"完了: {successful} 件成功"
        if failed > 0:
            status_text += f", {failed} 件失敗"
        
        self.after(0, lambda: self._set_status(status_text))
        self.after(0, lambda s=successful, f=failed: self._update_stats(s, f))
        
        # Enable folder button
        self.after(0, lambda: self.output_btn.configure(state="normal"))
    
    def _process_single_pdf(self, pdf_path: Path) -> dict:
        """Process a single PDF file - renames the original file in place"""
        try:
            # Extract text
            extracted_text = extract_text_from_pdf(pdf_path, self.vision_client)
            
            if not extracted_text:
                raise RuntimeError("テキストを抽出できませんでした")
            
            # Debug: Save extracted text to file for inspection
            debug_file = pdf_path.parent / f"{pdf_path.stem}_OCR_DEBUG.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            print(f"  - OCRテキストを保存: {debug_file.name}")
            
            # Parse text
            parsed_info = parse_extracted_text(extracted_text)
            
            # Generate filename
            new_filename = generate_new_filename(parsed_info, pdf_path.name)
            
            # Get unique filename in the SAME directory as original
            original_dir = pdf_path.parent
            unique_filename = get_unique_filename(original_dir, new_filename)
            
            # Rename file in place (overwrite original)
            new_path = original_dir / unique_filename
            pdf_path.rename(new_path)
            
            return {
                "success": True,
                "original": pdf_path.name,
                "new_name": unique_filename,
                "new_path": str(new_path),
                "parsed": {
                    "date": parsed_info["date"],
                    "material": parsed_info["material"],
                    "dimensions": parsed_info["dimensions"],
                    "manufacturer": parsed_info["manufacturer"],
                    "charge_no": parsed_info["charge_no"]
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "original": pdf_path.name,
                "error": str(e)
            }
    
    def _clear_results(self):
        """Clear all results from the scrollable frame"""
        for widget in self.results_scroll.winfo_children():
            widget.destroy()
        self.stats_label.configure(text="")
    
    def _add_result(self, result: dict):
        """Add a result item to the results list"""
        item = ResultItem(self.results_scroll, result)
        item.pack(fill="x", pady=(0, 8))
    
    def _update_stats(self, successful: int, failed: int):
        """Update the stats label"""
        total = successful + failed
        self.stats_label.configure(text=f"{successful}/{total} 件成功")
    
    def _update_progress(self, progress: float, status: str):
        """Update progress bar and status"""
        self.progress_bar.set(progress)
        self.status_label.configure(text=status)
    
    def _set_status(self, text: str, error: bool = False, show_progress: bool = False):
        """Set status bar text"""
        color = COLORS["error"] if error else COLORS["text_secondary"]
        self.status_label.configure(text=text, text_color=color)
        
        if show_progress:
            self.progress_bar.pack(side="right", padx=20, pady=15, fill="x", expand=True)
            self.progress_bar.set(0)
        else:
            self.progress_bar.pack_forget()


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point"""
    from dotenv import load_dotenv
    load_dotenv()
    
    app = MillsheetRenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
