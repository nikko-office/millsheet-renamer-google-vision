#!/usr/bin/env python3
"""
PDF Text Extraction and File Renaming Tool
Uses Google Cloud Vision API to extract Japanese text from PDFs
and renames files based on extracted date, company name, and document type
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from google.cloud import vision

# Load environment variables
load_dotenv()

# Configuration
INPUT_DIR = Path(os.getenv("PDF_INPUT_DIR", "./input"))
OUTPUT_DIR = Path(os.getenv("PDF_OUTPUT_DIR", "./output"))


# ============================================================================
# Google Vision API Client
# ============================================================================

def get_vision_client() -> vision.ImageAnnotatorClient:
    """Initialize Google Vision API client"""
    return vision.ImageAnnotatorClient()


# ============================================================================
# PDF to Image Conversion
# ============================================================================

def convert_pdf_page_to_image(pdf_path: Path, page_num: int = 1) -> Path:
    """
    Convert PDF page to PNG image using pdftoppm (Poppler)
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Page number to convert (1-indexed)
    
    Returns:
        Path to the generated image
    """
    temp_dir = tempfile.mkdtemp()
    output_base = Path(temp_dir) / f"page_{datetime.now().timestamp()}"
    
    # pdftoppm command: -png output format, -f/-l for page range, -r for DPI
    command = [
        "pdftoppm",
        "-png",
        "-f", str(page_num),
        "-l", str(page_num),
        "-r", "300",
        str(pdf_path),
        str(output_base)
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        # pdftoppm appends page number suffix
        generated_path = Path(f"{output_base}-{page_num}.png")
        
        if not generated_path.exists():
            raise FileNotFoundError(f"Generated image not found: {generated_path}")
        
        return generated_path
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"PDF to image conversion failed: {e.stderr}")


# ============================================================================
# Google Vision API Text Extraction
# ============================================================================

def extract_text_with_vision(image_path: Path, client: vision.ImageAnnotatorClient) -> str:
    """
    Extract text from image using Google Vision API
    Optimized for Japanese text recognition
    
    Args:
        image_path: Path to the image file
        client: Vision API client
    
    Returns:
        Extracted text
    """
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    image_context = vision.ImageContext(language_hints=["ja", "en"])
    
    response = client.document_text_detection(image=image, image_context=image_context)
    
    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")
    
    if not response.full_text_annotation:
        return ""
    
    return response.full_text_annotation.text or ""


def extract_text_from_pdf(pdf_path: Path, client: vision.ImageAnnotatorClient) -> str:
    """
    Extract text from PDF using Vision API (converts to image first)
    
    Args:
        pdf_path: Path to the PDF file
        client: Vision API client
    
    Returns:
        Extracted text
    """
    image_path = None
    
    try:
        # Convert first page to image
        image_path = convert_pdf_page_to_image(pdf_path, 1)
        
        # Extract text using Vision API
        text = extract_text_with_vision(image_path, client)
        
        return text
        
    finally:
        # Cleanup temporary image and directory
        if image_path and image_path.exists():
            temp_dir = image_path.parent
            shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Text Parsing - Extract Date, Company Name, Document Type
# ============================================================================

def extract_date(text: str) -> Optional[str]:
    """
    Extract date from Japanese text
    Supports formats: 2024年1月15日, 2024/01/15, 2024-01-15, R6.1.15, 令和6年1月15日
    
    Args:
        text: Extracted text
    
    Returns:
        Formatted date (YYYY-MM-DD) or None
    """
    patterns = [
        # 2024年1月15日 or 2024年01月15日
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', None),
        # 2024/01/15 or 2024/1/15
        (r'(\d{4})[/](\d{1,2})[/](\d{1,2})', None),
        # 2024-01-15
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', None),
        # 令和6年1月15日 (Japanese era)
        (r'令和(\d{1,2})年(\d{1,2})月(\d{1,2})日', 'reiwa'),
        # R6.1.15 or R06.01.15
        (r'R(\d{1,2})\.(\d{1,2})\.(\d{1,2})', 'reiwa'),
        # 平成31年1月15日
        (r'平成(\d{1,2})年(\d{1,2})月(\d{1,2})日', 'heisei'),
    ]
    
    for pattern, era_type in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if era_type == 'reiwa':
                # Convert Reiwa era to Western year (Reiwa 1 = 2019)
                year = 2018 + int(match.group(1))
            elif era_type == 'heisei':
                # Convert Heisei era to Western year (Heisei 1 = 1989)
                year = 1988 + int(match.group(1))
            else:
                year = int(match.group(1))
            
            month = int(match.group(2))
            day = int(match.group(3))
            
            # Format as YYYY-MM-DD
            return f"{year}-{month:02d}-{day:02d}"
    
    return None


def extract_company_name(text: str) -> Optional[str]:
    """
    Extract company name from Japanese text
    Looks for common patterns in business documents
    
    Args:
        text: Extracted text
    
    Returns:
        Company name or None
    """
    patterns = [
        # Company name patterns with suffixes
        r'([^\s\n]{2,20}(?:株式会社|有限会社|合同会社|㈱|㈲))',
        r'(?:株式会社|有限会社|合同会社)([^\s\n]{2,20})',
        # Pattern: 会社名：XXX or 会社名:XXX
        r'会社名[：:]\s*([^\n]+)',
        # Pattern: 製造者：XXX
        r'製造者[：:]\s*([^\n]+)',
        # Pattern: 販売者：XXX
        r'販売者[：:]\s*([^\n]+)',
        # Pattern: 発行者：XXX
        r'発行[者元][：:]\s*([^\n]+)',
        # Pattern: メーカー：XXX
        r'メーカー[：:]\s*([^\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company_name = match.group(1).strip()
            # Filter out unlikely matches
            if 2 <= len(company_name) <= 30:
                return company_name
    
    return None


def extract_document_type(text: str) -> str:
    """
    Extract document type from Japanese text
    Common types: ミルシート, 検査証明書, 成績表, 納品書, etc.
    
    Args:
        text: Extracted text
    
    Returns:
        Document type or 'document'
    """
    document_types = [
        (r'ミルシート|MILL\s*SHEET', 'ミルシート'),
        (r'検査[証成][明績]書', '検査証明書'),
        (r'試験成績[書表]', '試験成績書'),
        (r'材料証明書', '材料証明書'),
        (r'品質証明書', '品質証明書'),
        (r'納品書', '納品書'),
        (r'請求書', '請求書'),
        (r'見積書', '見積書'),
        (r'注文書', '注文書'),
        (r'仕様書', '仕様書'),
        (r'成績表', '成績表'),
        (r'証明書', '証明書'),
    ]
    
    for pattern, doc_type in document_types:
        if re.search(pattern, text, re.IGNORECASE):
            return doc_type
    
    return 'document'


def parse_extracted_text(text: str) -> dict:
    """
    Parse all relevant information from extracted text
    
    Args:
        text: Full extracted text
    
    Returns:
        Dictionary with parsed information
    """
    return {
        'date': extract_date(text),
        'company_name': extract_company_name(text),
        'document_type': extract_document_type(text),
        'raw_text': text
    }


# ============================================================================
# File Naming and Processing
# ============================================================================

def sanitize_for_filename(text: Optional[str]) -> str:
    """
    Sanitize text for use as filename
    
    Args:
        text: Text to sanitize
    
    Returns:
        Safe filename string
    """
    if not text:
        return ''
    
    # Replace newlines with spaces
    result = re.sub(r'[\r\n]+', ' ', text)
    # Replace invalid filename characters
    result = re.sub(r'[\\/:*?"<>|]', '_', result)
    # Replace whitespace with underscores
    result = re.sub(r'\s+', '_', result)
    # Replace multiple underscores with single
    result = re.sub(r'_+', '_', result)
    # Remove leading/trailing underscores
    result = result.strip('_')
    
    return result[:50]


def generate_new_filename(info: dict, original_name: str) -> str:
    """
    Generate new filename based on extracted information
    Format: [DATE]_[COMPANY]_[DOCTYPE].pdf
    
    Args:
        info: Parsed information
        original_name: Original filename (fallback)
    
    Returns:
        New filename
    """
    parts = []
    
    # Add date if found
    if info['date']:
        parts.append(info['date'])
    
    # Add company name if found
    if info['company_name']:
        parts.append(sanitize_for_filename(info['company_name']))
    
    # Add document type
    parts.append(sanitize_for_filename(info['document_type']))
    
    # If no meaningful parts, use original name
    if not parts or (len(parts) == 1 and parts[0] == 'document'):
        base_name = Path(original_name).stem
        return f"{sanitize_for_filename(base_name)}_renamed.pdf"
    
    return f"{'_'.join(parts)}.pdf"


def get_unique_filename(directory: Path, filename: str) -> str:
    """
    Get unique filename (add counter if file exists)
    
    Args:
        directory: Directory path
        filename: Desired filename
    
    Returns:
        Unique filename
    """
    path = Path(filename)
    ext = path.suffix
    base = path.stem
    
    final_name = filename
    counter = 1
    
    while (directory / final_name).exists():
        final_name = f"{base}_{counter}{ext}"
        counter += 1
    
    return final_name


def process_pdf(pdf_path: Path, client: vision.ImageAnnotatorClient) -> dict:
    """
    Process a single PDF file
    
    Args:
        pdf_path: Path to the PDF file
        client: Vision API client
    
    Returns:
        Processing result dictionary
    """
    original_name = pdf_path.name
    
    print(f"\n処理中: {original_name}")
    
    try:
        # Step 1: Extract text using Vision API
        print("  - Google Vision APIでテキスト抽出中...")
        extracted_text = extract_text_from_pdf(pdf_path, client)
        
        if not extracted_text:
            raise RuntimeError("PDFからテキストを抽出できませんでした")
        
        # Step 2: Parse extracted information
        print("  - 抽出テキストを解析中...")
        parsed_info = parse_extracted_text(extracted_text)
        
        print(f"    日付: {parsed_info['date'] or '見つかりません'}")
        print(f"    会社名: {parsed_info['company_name'] or '見つかりません'}")
        print(f"    文書タイプ: {parsed_info['document_type']}")
        
        # Step 3: Generate new filename
        new_filename = generate_new_filename(parsed_info, original_name)
        unique_filename = get_unique_filename(OUTPUT_DIR, new_filename)
        
        # Step 4: Copy file with new name
        output_path = OUTPUT_DIR / unique_filename
        shutil.copy2(pdf_path, output_path)
        
        print(f"  - 新しいファイル名: {unique_filename}")
        
        return {
            'success': True,
            'original': original_name,
            'new_name': unique_filename,
            'parsed': {
                'date': parsed_info['date'],
                'company': parsed_info['company_name'],
                'type': parsed_info['document_type']
            }
        }
        
    except Exception as e:
        print(f"  - エラー: {e}")
        return {
            'success': False,
            'original': original_name,
            'error': str(e)
        }


# ============================================================================
# Directory Operations
# ============================================================================

def ensure_directories():
    """Ensure all required directories exist"""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_pdf_files() -> list[Path]:
    """
    Get all PDF files from input directory
    
    Returns:
        List of PDF file paths
    """
    return sorted([
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == '.pdf'
    ])


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point"""
    print("═" * 60)
    print("  PDF テキスト抽出・ファイル名変更ツール")
    print("  Google Cloud Vision API を使用した日本語OCR")
    print("═" * 60)
    
    try:
        # Setup
        ensure_directories()
        
        # Initialize Vision API client
        client = get_vision_client()
        
        # Get PDF files
        pdf_files = get_pdf_files()
        
        if not pdf_files:
            print(f"\n{INPUT_DIR} にPDFファイルが見つかりません")
            print("PDFファイルをinputディレクトリに配置してから再実行してください。")
            return
        
        print(f"\n{len(pdf_files)} 個のPDFファイルを処理します")
        
        # Process each PDF
        results = []
        for pdf_file in pdf_files:
            result = process_pdf(pdf_file, client)
            results.append(result)
        
        # Print summary
        print("\n" + "═" * 60)
        print("  処理結果サマリー")
        print("═" * 60)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\n合計: {len(results)} | 成功: {len(successful)} | 失敗: {len(failed)}")
        
        if successful:
            print("\n✓ 名前変更成功:")
            for r in successful:
                print(f"  {r['original']}")
                print(f"    → {r['new_name']}")
        
        if failed:
            print("\n✗ 失敗:")
            for r in failed:
                print(f"  {r['original']}: {r['error']}")
        
        print(f"\n出力ディレクトリ: {OUTPUT_DIR.resolve()}")
        
    except Exception as e:
        print(f"\n致命的なエラー: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
