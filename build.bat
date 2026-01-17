@echo off
chcp 65001 > nul
echo ════════════════════════════════════════════════════════════
echo   ミルシートリネーマー - EXEビルドスクリプト
echo ════════════════════════════════════════════════════════════
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo [1/4] 仮想環境を有効化中...
    call venv\Scripts\activate.bat
) else (
    echo [!] 仮想環境が見つかりません。グローバルPythonを使用します。
)

echo [2/4] 依存関係を確認中...
pip install -r requirements.txt -q

echo [3/4] EXEファイルをビルド中...
pyinstaller --noconfirm millsheet_renamer.spec

echo [4/4] ビルド完了！
echo.
echo ════════════════════════════════════════════════════════════
echo   出力先: dist\MillsheetRenamer\MillsheetRenamer.exe
echo ════════════════════════════════════════════════════════════
echo.

if exist "dist\MillsheetRenamer\MillsheetRenamer.exe" (
    echo EXEファイルが正常に作成されました。
    echo.
    set /p OPEN_FOLDER="出力フォルダを開きますか？ (y/n): "
    if /i "%OPEN_FOLDER%"=="y" (
        explorer "dist\MillsheetRenamer"
    )
) else (
    echo [エラー] ビルドに失敗しました。
)

pause
