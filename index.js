/**
 * PDF Text Extraction and File Renaming Tool
 * Uses Google Cloud Vision API to extract Japanese text from PDFs
 * and renames files based on extracted date, company name, and document type
 */

require('dotenv').config();
const vision = require('@google-cloud/vision');
const pdf = require('pdf-parse');
const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

// Configuration
const INPUT_DIR = process.env.PDF_INPUT_DIR || './input';
const OUTPUT_DIR = process.env.PDF_OUTPUT_DIR || './output';
const TEMP_DIR = './temp';

// Initialize Google Vision API client
const visionClient = new vision.ImageAnnotatorClient();

// ============================================================================
// PDF to Image Conversion
// ============================================================================

/**
 * Convert PDF page to PNG image using pdftoppm (Poppler)
 * @param {string} pdfPath - Path to the PDF file
 * @param {number} pageNum - Page number to convert (1-indexed)
 * @returns {Promise<string>} - Path to the generated image
 */
async function convertPdfPageToImage(pdfPath, pageNum = 1) {
    const timestamp = Date.now();
    const outputBase = path.join(TEMP_DIR, `page_${timestamp}`);

    // pdftoppm command: -png output format, -f/-l for page range, -r for DPI
    const command = `pdftoppm -png -f ${pageNum} -l ${pageNum} -r 300 "${pdfPath}" "${outputBase}"`;

    try {
        await execAsync(command);
        // pdftoppm appends page number suffix
        const generatedPath = `${outputBase}-${pageNum}.png`;
        await fs.access(generatedPath);
        return generatedPath;
    } catch (error) {
        throw new Error(`PDF to image conversion failed: ${error.message}`);
    }
}

// ============================================================================
// Google Vision API Text Extraction
// ============================================================================

/**
 * Extract text from image using Google Vision API
 * Optimized for Japanese text recognition
 * @param {string} imagePath - Path to the image file
 * @returns {Promise<string>} - Extracted text
 */
async function extractTextWithVision(imagePath) {
    const imageBuffer = await fs.readFile(imagePath);

    const request = {
        image: { content: imageBuffer.toString('base64') },
        imageContext: {
            languageHints: ['ja', 'en']  // Prioritize Japanese
        }
    };

    const [result] = await visionClient.documentTextDetection(request);

    if (!result.fullTextAnnotation) {
        return '';
    }

    return result.fullTextAnnotation.text || '';
}

/**
 * Extract text from PDF using Vision API (converts to image first)
 * @param {string} pdfPath - Path to the PDF file
 * @returns {Promise<string>} - Extracted text
 */
async function extractTextFromPdf(pdfPath) {
    let imagePath = null;

    try {
        // Convert first page to image
        imagePath = await convertPdfPageToImage(pdfPath, 1);

        // Extract text using Vision API
        const text = await extractTextWithVision(imagePath);

        return text;
    } finally {
        // Cleanup temporary image
        if (imagePath) {
            await fs.unlink(imagePath).catch(() => {});
        }
    }
}

// ============================================================================
// Text Parsing - Extract Date, Company Name, Document Type
// ============================================================================

/**
 * Extract date from Japanese text
 * Supports formats: 2024年1月15日, 2024/01/15, 2024-01-15, R6.1.15, 令和6年1月15日
 * @param {string} text - Extracted text
 * @returns {string|null} - Formatted date (YYYY-MM-DD) or null
 */
function extractDate(text) {
    const patterns = [
        // 2024年1月15日 or 2024年01月15日
        /(\d{4})年(\d{1,2})月(\d{1,2})日/,
        // 2024/01/15 or 2024/1/15
        /(\d{4})[\/](\d{1,2})[\/](\d{1,2})/,
        // 2024-01-15
        /(\d{4})-(\d{1,2})-(\d{1,2})/,
        // 令和6年1月15日 (Japanese era)
        /令和(\d{1,2})年(\d{1,2})月(\d{1,2})日/,
        // R6.1.15 or R06.01.15
        /R(\d{1,2})\.(\d{1,2})\.(\d{1,2})/i,
        // 平成31年1月15日
        /平成(\d{1,2})年(\d{1,2})月(\d{1,2})日/,
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match) {
            let year, month, day;

            if (pattern.source.includes('令和') || pattern.source.includes('R')) {
                // Convert Reiwa era to Western year (Reiwa 1 = 2019)
                year = 2018 + parseInt(match[1]);
                month = match[2];
                day = match[3];
            } else if (pattern.source.includes('平成')) {
                // Convert Heisei era to Western year (Heisei 1 = 1989)
                year = 1988 + parseInt(match[1]);
                month = match[2];
                day = match[3];
            } else {
                year = match[1];
                month = match[2];
                day = match[3];
            }

            // Format as YYYY-MM-DD
            return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        }
    }

    return null;
}

/**
 * Extract company name from Japanese text
 * Looks for common patterns in business documents
 * @param {string} text - Extracted text
 * @returns {string|null} - Company name or null
 */
function extractCompanyName(text) {
    const patterns = [
        // Company name patterns with suffixes
        /([^\s\n]{2,20}(?:株式会社|有限会社|合同会社|㈱|㈲))/,
        /(?:株式会社|有限会社|合同会社)([^\s\n]{2,20})/,
        // Pattern: 会社名：XXX or 会社名:XXX
        /会社名[：:]\s*([^\n]+)/,
        // Pattern: 製造者：XXX
        /製造者[：:]\s*([^\n]+)/,
        // Pattern: 販売者：XXX
        /販売者[：:]\s*([^\n]+)/,
        // Pattern: 発行者：XXX
        /発行[者元][：:]\s*([^\n]+)/,
        // Pattern: メーカー：XXX
        /メーカー[：:]\s*([^\n]+)/,
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match) {
            const companyName = match[1].trim();
            // Filter out unlikely matches
            if (companyName.length >= 2 && companyName.length <= 30) {
                return companyName;
            }
        }
    }

    return null;
}

/**
 * Extract document type from Japanese text
 * Common types: ミルシート, 検査証明書, 成績表, 納品書, etc.
 * @param {string} text - Extracted text
 * @returns {string} - Document type or 'document'
 */
function extractDocumentType(text) {
    const documentTypes = [
        { pattern: /ミルシート|MILL\s*SHEET/i, type: 'ミルシート' },
        { pattern: /検査[証成][明績]書/, type: '検査証明書' },
        { pattern: /試験成績[書表]/, type: '試験成績書' },
        { pattern: /材料証明書/, type: '材料証明書' },
        { pattern: /品質証明書/, type: '品質証明書' },
        { pattern: /納品書/, type: '納品書' },
        { pattern: /請求書/, type: '請求書' },
        { pattern: /見積書/, type: '見積書' },
        { pattern: /注文書/, type: '注文書' },
        { pattern: /仕様書/, type: '仕様書' },
        { pattern: /成績表/, type: '成績表' },
        { pattern: /証明書/, type: '証明書' },
    ];

    for (const { pattern, type } of documentTypes) {
        if (pattern.test(text)) {
            return type;
        }
    }

    return 'document';
}

/**
 * Parse all relevant information from extracted text
 * @param {string} text - Full extracted text
 * @returns {Object} - Parsed information
 */
function parseExtractedText(text) {
    return {
        date: extractDate(text),
        companyName: extractCompanyName(text),
        documentType: extractDocumentType(text),
        rawText: text
    };
}

// ============================================================================
// File Naming and Processing
// ============================================================================

/**
 * Sanitize text for use as filename
 * @param {string} text - Text to sanitize
 * @returns {string} - Safe filename string
 */
function sanitizeForFilename(text) {
    if (!text) return '';

    return text
        .replace(/[\r\n]+/g, ' ')
        .replace(/[\\/:*?"<>|]/g, '_')
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '')
        .trim()
        .substring(0, 50);
}

/**
 * Generate new filename based on extracted information
 * Format: [DATE]_[COMPANY]_[DOCTYPE].pdf
 * @param {Object} info - Parsed information
 * @param {string} originalName - Original filename (fallback)
 * @returns {string} - New filename
 */
function generateNewFilename(info, originalName) {
    const parts = [];

    // Add date if found
    if (info.date) {
        parts.push(info.date);
    }

    // Add company name if found
    if (info.companyName) {
        parts.push(sanitizeForFilename(info.companyName));
    }

    // Add document type
    parts.push(sanitizeForFilename(info.documentType));

    // If no meaningful parts, use original name
    if (parts.length === 0 || (parts.length === 1 && parts[0] === 'document')) {
        const baseName = path.basename(originalName, '.pdf');
        return `${sanitizeForFilename(baseName)}_renamed.pdf`;
    }

    return `${parts.join('_')}.pdf`;
}

/**
 * Get unique filename (add counter if file exists)
 * @param {string} dir - Directory path
 * @param {string} filename - Desired filename
 * @returns {Promise<string>} - Unique filename
 */
async function getUniqueFilename(dir, filename) {
    const ext = path.extname(filename);
    const base = path.basename(filename, ext);

    let finalName = filename;
    let counter = 1;

    while (true) {
        try {
            await fs.access(path.join(dir, finalName));
            // File exists, try with counter
            finalName = `${base}_${counter}${ext}`;
            counter++;
        } catch {
            // File doesn't exist, use this name
            return finalName;
        }
    }
}

/**
 * Process a single PDF file
 * @param {string} pdfPath - Path to the PDF file
 * @returns {Promise<Object>} - Processing result
 */
async function processPdf(pdfPath) {
    const originalName = path.basename(pdfPath);

    console.log(`\nProcessing: ${originalName}`);

    try {
        // Step 1: Extract text using Vision API
        console.log('  - Extracting text with Google Vision API...');
        const extractedText = await extractTextFromPdf(pdfPath);

        if (!extractedText) {
            throw new Error('No text could be extracted from the PDF');
        }

        // Step 2: Parse extracted information
        console.log('  - Parsing extracted text...');
        const parsedInfo = parseExtractedText(extractedText);

        console.log(`    Date: ${parsedInfo.date || 'Not found'}`);
        console.log(`    Company: ${parsedInfo.companyName || 'Not found'}`);
        console.log(`    Type: ${parsedInfo.documentType}`);

        // Step 3: Generate new filename
        const newFilename = generateNewFilename(parsedInfo, originalName);
        const uniqueFilename = await getUniqueFilename(OUTPUT_DIR, newFilename);

        // Step 4: Copy file with new name
        const outputPath = path.join(OUTPUT_DIR, uniqueFilename);
        await fs.copyFile(pdfPath, outputPath);

        console.log(`  - Renamed to: ${uniqueFilename}`);

        return {
            success: true,
            original: originalName,
            newName: uniqueFilename,
            parsed: {
                date: parsedInfo.date,
                company: parsedInfo.companyName,
                type: parsedInfo.documentType
            }
        };

    } catch (error) {
        console.error(`  - Error: ${error.message}`);
        return {
            success: false,
            original: originalName,
            error: error.message
        };
    }
}

// ============================================================================
// Directory Operations
// ============================================================================

/**
 * Ensure all required directories exist
 */
async function ensureDirectories() {
    const dirs = [INPUT_DIR, OUTPUT_DIR, TEMP_DIR];
    for (const dir of dirs) {
        await fs.mkdir(dir, { recursive: true });
    }
}

/**
 * Get all PDF files from input directory
 * @returns {Promise<string[]>} - Array of PDF file paths
 */
async function getPdfFiles() {
    const entries = await fs.readdir(INPUT_DIR, { withFileTypes: true });

    return entries
        .filter(entry => entry.isFile() && entry.name.toLowerCase().endsWith('.pdf'))
        .map(entry => path.join(INPUT_DIR, entry.name));
}

/**
 * Cleanup temporary files
 */
async function cleanup() {
    try {
        await fs.rm(TEMP_DIR, { recursive: true, force: true });
    } catch {
        // Ignore cleanup errors
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

async function main() {
    console.log('═'.repeat(60));
    console.log('  PDF Text Extraction and Renaming Tool');
    console.log('  Using Google Cloud Vision API for Japanese OCR');
    console.log('═'.repeat(60));

    try {
        // Setup
        await ensureDirectories();

        // Get PDF files
        const pdfFiles = await getPdfFiles();

        if (pdfFiles.length === 0) {
            console.log(`\nNo PDF files found in ${INPUT_DIR}`);
            console.log('Place PDF files in the input directory and run again.');
            return;
        }

        console.log(`\nFound ${pdfFiles.length} PDF file(s) to process`);

        // Process each PDF
        const results = [];
        for (const pdfFile of pdfFiles) {
            const result = await processPdf(pdfFile);
            results.push(result);
        }

        // Print summary
        console.log('\n' + '═'.repeat(60));
        console.log('  SUMMARY');
        console.log('═'.repeat(60));

        const successful = results.filter(r => r.success);
        const failed = results.filter(r => !r.success);

        console.log(`\nTotal: ${results.length} | Success: ${successful.length} | Failed: ${failed.length}`);

        if (successful.length > 0) {
            console.log('\nSuccessfully renamed:');
            successful.forEach(r => {
                console.log(`  ${r.original}`);
                console.log(`    → ${r.newName}`);
            });
        }

        if (failed.length > 0) {
            console.log('\nFailed:');
            failed.forEach(r => {
                console.log(`  ${r.original}: ${r.error}`);
            });
        }

        console.log(`\nOutput directory: ${path.resolve(OUTPUT_DIR)}`);

    } catch (error) {
        console.error('\nFatal error:', error.message);
        process.exit(1);
    } finally {
        await cleanup();
    }
}

// Run
main();

// Export for testing
module.exports = {
    extractDate,
    extractCompanyName,
    extractDocumentType,
    parseExtractedText,
    sanitizeForFilename,
    generateNewFilename
};
