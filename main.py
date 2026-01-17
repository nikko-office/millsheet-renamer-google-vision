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
# Text Parsing - Extract Date, Material, Dimensions, Manufacturer
# For Mill Sheets / Inspection Certificates
# ============================================================================

# Priority manufacturers (these take precedence over other company names)
PRIORITY_MANUFACTURERS = [
    ('東京製鉄', ['東京製鉄', '東京製鐵', '東京製鉄所', '東京製鐵所', 'TOKYO STEEL', 'TOKYOSTEEL']),
    ('中山製鋼', ['中山製鋼', '中山製鉄', '中山製鋼所', '中山製鉄所', 'NAKAYAMA STEEL', 'NAKAYAMA']),
    ('神戸製鋼', ['神戸製鋼', '神戸製鉄', '神戸製鋼所', '神戸製鉄所', 'KOBE STEEL', 'KOBELCO']),
]


def extract_date(text: str) -> Optional[str]:
    """
    Extract issue date from Japanese text (発行日)
    Supports formats: 2024年1月15日, 2024/01/15, 2024-01-15, R6.1.15, 令和6年1月15日
    Also supports English formats: AUG . 04 . 2025, Aug 04, 2025, etc.
    
    Args:
        text: Extracted text
    
    Returns:
        Formatted date (YY-MM-DD) or None
    """
    # English month name mapping
    month_map = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'JUNE': 6,
        'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
    }
    
    year = None
    month = None
    day = None
    
    # Pattern 1: English month format (AUG . 04 . 2025, Aug 04, 2025, AUG-04-2025, etc.)
    eng_patterns = [
        # AUG . 04 . 2025 or AUG.04.2025
        r'([A-Z]{3,9})\s*[.\-/,]\s*(\d{1,2})\s*[.\-/,]\s*(\d{4})',
        # 04 AUG 2025 or 04-AUG-2025
        r'(\d{1,2})\s*[.\-/,]\s*([A-Z]{3,9})\s*[.\-/,]\s*(\d{4})',
        # 2025.AUG.04 or 2025-AUG-04
        r'(\d{4})\s*[.\-/,]\s*([A-Z]{3,9})\s*[.\-/,]\s*(\d{1,2})',
    ]
    
    for i, pattern in enumerate(eng_patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if i == 0:  # MON DD YYYY
                month_str, day_str, year_str = groups
                month = month_map.get(month_str.upper())
                day = int(day_str)
                year = int(year_str)
            elif i == 1:  # DD MON YYYY
                day_str, month_str, year_str = groups
                month = month_map.get(month_str.upper())
                day = int(day_str)
                year = int(year_str)
            elif i == 2:  # YYYY MON DD
                year_str, month_str, day_str = groups
                month = month_map.get(month_str.upper())
                day = int(day_str)
                year = int(year_str)
            
            if year and month and day:
                # Format as YY-MM-DD (2-digit year)
                return f"{year % 100:02d}-{month:02d}-{day:02d}"
    
    # Japanese/numeric patterns
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
            
            # Format as YY-MM-DD (2-digit year)
            return f"{year % 100:02d}-{month:02d}-{day:02d}"
    
    return None


def extract_material(text: str) -> Optional[str]:
    """
    Extract material/steel grade from mill sheet text (材質)
    Common grades: SS400, SPHC, SPCC, S45C, SUS304, etc.
    
    Args:
        text: Extracted text
    
    Returns:
        Material grade or None
    """
    # Steel grade patterns (common Japanese/JIS standards)
    patterns = [
        # SS series (general structural steel)
        r'\b(SS\s*[234]\d{2})\b',
        # SPHC, SPCC, SPCD, SPCE (hot/cold rolled steel)
        r'\b(SPH[CDE]|SPC[CDE])\b',
        # SECC, SECD (electro-galvanized)
        r'\b(SEC[CD])\b',
        # SGCC, SGHC (hot-dip galvanized)
        r'\b(SG[CH]C)\b',
        # S-C series (carbon steel for machine structural use)
        r'\b(S\d{2}C)\b',
        # SCM series (chromium molybdenum steel)
        r'\b(SCM\d{3})\b',
        # SUS series (stainless steel)
        r'\b(SUS\s*\d{3}[A-Z]?)\b',
        # SK series (carbon tool steel)
        r'\b(SK\d{1,2})\b',
        # SM series (welded structural steel)
        r'\b(SM\d{3}[A-C]?)\b',
        # STK series (carbon steel tubes)
        r'\b(STK\d{3})\b',
        # STKR series (rectangular tubes)
        r'\b(STKR\d{3})\b',
        # Generic pattern for other grades
        r'\b(S[A-Z]{1,3}\d{2,3}[A-Z]?)\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            material = match.group(1).upper().replace(' ', '')
            return material
    
    return None


def extract_dimensions(text: str) -> Optional[str]:
    """
    Extract dimensions from mill sheet text (寸法)
    Formats: 厚さ x 幅 x 長さ/COIL, t1.6 x 1219 x C, etc.
    
    Mill sheet dimensions typically have:
    - Thickness: small number (0.1 - 100mm)
    - Width: larger number (100 - 3000mm)  
    - Length: even larger or COIL
    
    Args:
        text: Extracted text
    
    Returns:
        Dimensions string or None
    """
    
    def is_valid_dimension(thickness_str, width_str, length_str=None):
        """Check if dimensions are realistic for steel sheets"""
        try:
            # Remove commas from numbers (e.g., 1,535 -> 1535)
            thickness = float(str(thickness_str).replace(',', ''))
            width = float(str(width_str).replace(',', ''))
            # Thickness should be small (0.1-100mm), width should be larger (100-5000mm)
            # Width should be significantly larger than thickness
            if thickness < 0.1 or thickness > 100:
                return False
            if width < 100 or width > 5000:
                return False
            if width <= thickness:
                return False
            # Length check: skip if COIL/C, otherwise must be >= 100
            if length_str:
                length_upper = str(length_str).upper()
                if length_upper not in ['COIL', 'コイル', 'C']:
                    try:
                        length = float(str(length_str).replace(',', ''))
                        if length < 100:
                            return False
                    except ValueError:
                        # Non-numeric length that's not COIL - still valid
                        pass
            return True
        except (ValueError, TypeError):
            return False
    
    # Priority 1: Look near DIMENSIONS or 寸法 label
    dimension_section = None
    dim_match = re.search(r'(?:DIMENSIONS?|寸法)[^\n]*\n?([^\n]+)', text, re.IGNORECASE)
    if dim_match:
        dimension_section = dim_match.group(0) + dim_match.group(1)
    
    # Dimension patterns (ordered by specificity)
    # Note: Width may contain comma (e.g., 1,535) which needs to be handled
    patterns = [
        # Pattern: 1.60X1,535XCOIL (with comma in width) - HIGHEST PRIORITY for Tokyo Steel
        r'(\d+\.?\d*)\s*[x×X]\s*(\d{1,2},\d{3})\s*[x×X]\s*(COIL|コイル|C)\b',
        # Pattern: 1.6x1535xCOIL (thickness x width x COIL/C)
        r'(\d+\.?\d*)\s*[x×X]\s*(\d{3,4})\s*[x×X]\s*(COIL|コイル|C)\b',
        # Pattern: 1.6X1219X2438 (thickness x width x length - common in tables)
        r'(\d+\.?\d*)\s*[x×X]\s*(\d{3,4})\s*[x×X]\s*(\d{3,4})',
        # Pattern: with comma in width for numeric length
        r'(\d+\.?\d*)\s*[x×X]\s*(\d{1,2},\d{3})\s*[x×X]\s*(\d{3,4})',
        # Pattern: 22.00x1.540xCOIL (with decimal width)
        r'(\d+\.?\d*)\s*[x×X]\s*(\d+\.?\d*)\s*[x×X]\s*(COIL|コイル|C)\b',
        # Pattern: t1.6 x 1219 x COIL or t1.6x1219xCOIL
        r't\s*(\d+\.?\d*)\s*[x×X]\s*(\d+\.?\d*)\s*[x×X]\s*(COIL|コイル|C|\d+\.?\d*)',
        # Pattern: generic AxBxC (thickness x width x length)
        r'(\d+\.?\d*)\s*[x×X]\s*(\d+\.?\d*)\s*[x×X]\s*(\d+\.?\d*)',
        # Pattern: 板厚1.6 幅1219
        r'板厚\s*(\d+\.?\d*)\s*.*?幅\s*(\d+\.?\d*)',
        # Pattern: 1.6t x 1219W or 1.6tx1219W
        r'(\d+\.?\d*)\s*[tT]\s*[x×X]\s*(\d+\.?\d*)\s*[wW]?',
    ]
    
    # First try to find in dimension section
    search_texts = [dimension_section, text] if dimension_section else [text]
    
    for search_text in search_texts:
        if not search_text:
            continue
            
        for pattern in patterns:
            matches = re.finditer(pattern, search_text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) == 3:
                    thickness = groups[0]
                    width = groups[1].replace(',', '')  # Remove comma from width
                    length = groups[2]
                    
                    # Validate dimensions
                    if is_valid_dimension(thickness, width, length):
                        # Normalize COIL/コイル to C
                        if length.upper() in ['COIL', 'コイル']:
                            length = 'C'
                        return f"{thickness}x{width}x{length}"
                        
                elif len(groups) == 2:
                    thickness = groups[0]
                    width = groups[1].replace(',', '')  # Remove comma from width
                    if is_valid_dimension(thickness, width):
                        return f"{thickness}x{width}"
    
    return None


def extract_charge_no(text: str) -> Optional[str]:
    """
    Extract charge number (溶鋼番号/鋼番) from mill sheet text
    
    Args:
        text: Extracted text
    
    Returns:
        Charge number or None
    """
    # Patterns for charge number
    patterns = [
        # Near label: 溶鋼番号, CHARGE No, 鋼番
        r'(?:溶[鋼銅]番号|CHARGE\s*N[oO]\.?|鋼番)\s*[:\s]*([A-Z0-9]{4,12})',
        # Pattern: alphanumeric 5-10 chars that looks like charge no (e.g., 5E20142, AD8075)
        r'\b([A-Z]{1,2}\d{4,8})\b',
        r'\b(\d{1,2}[A-Z]\d{4,6})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            charge_no = match.group(1).upper()
            # Validate: should be 5-12 chars, alphanumeric
            if 4 <= len(charge_no) <= 12 and charge_no.isalnum():
                return charge_no
    
    return None


def extract_manufacturer(text: str) -> Optional[str]:
    """
    Extract manufacturer name from mill sheet text (メーカー名)
    Priority: 東京製鉄, 中山製鋼, 神戸製鋼
    
    Args:
        text: Extracted text
    
    Returns:
        Manufacturer name or None
    """
    # First, check for priority manufacturers
    for display_name, variants in PRIORITY_MANUFACTURERS:
        for variant in variants:
            if variant.upper() in text.upper():
                return display_name
    
    # If no priority manufacturer found, try to find other company names
    patterns = [
        # Company name patterns with suffixes
        r'([^\s\n]{2,15}(?:製鉄|製鋼|製鐵))',
        r'([^\s\n]{2,15}(?:株式会社|㈱))',
        r'(?:製造者|メーカー)[：:]\s*([^\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            if 2 <= len(name) <= 20:
                return name
    
    return None


def parse_extracted_text(text: str) -> dict:
    """
    Parse mill sheet information from extracted text
    
    Args:
        text: Full extracted text
    
    Returns:
        Dictionary with parsed information:
        - date: 発行日
        - material: 材質
        - dimensions: 寸法
        - manufacturer: メーカー名
        - charge_no: 溶鋼番号
    """
    return {
        'date': extract_date(text),
        'material': extract_material(text),
        'dimensions': extract_dimensions(text),
        'manufacturer': extract_manufacturer(text),
        'charge_no': extract_charge_no(text),
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
    Generate new filename based on extracted mill sheet information
    Format: [発行日]_[材質]_[寸法]_[メーカー名]_[Charge No].pdf
    
    Args:
        info: Parsed information (date, material, dimensions, manufacturer, charge_no)
        original_name: Original filename (fallback)
    
    Returns:
        New filename
    """
    parts = []
    
    # Add date (発行日) if found
    if info.get('date'):
        parts.append(info['date'])
    
    # Add material (材質) if found
    if info.get('material'):
        parts.append(sanitize_for_filename(info['material']))
    
    # Add dimensions (寸法) if found
    if info.get('dimensions'):
        parts.append(sanitize_for_filename(info['dimensions']))
    
    # Add manufacturer (メーカー名) if found
    if info.get('manufacturer'):
        parts.append(sanitize_for_filename(info['manufacturer']))
    
    # Add charge number (溶鋼番号) if found
    if info.get('charge_no'):
        parts.append(sanitize_for_filename(info['charge_no']))
    
    # If no meaningful parts, use original name
    if not parts:
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
        
        print(f"    発行日: {parsed_info['date'] or '見つかりません'}")
        print(f"    材質: {parsed_info['material'] or '見つかりません'}")
        print(f"    寸法: {parsed_info['dimensions'] or '見つかりません'}")
        print(f"    メーカー: {parsed_info['manufacturer'] or '見つかりません'}")
        print(f"    Charge No: {parsed_info['charge_no'] or '見つかりません'}")
        
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
                'material': parsed_info['material'],
                'dimensions': parsed_info['dimensions'],
                'manufacturer': parsed_info['manufacturer'],
                'charge_no': parsed_info['charge_no']
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
