@echo off
chcp 65001 > nul
echo ════════════════════════════════════════════════════════════
echo   ミルシートリネーマー - EXEビルドスクリプト
echo ════════════════════════════════════════════════════════════
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo [1/6] 仮想環境を有効化中...
    call venv\Scripts\activate.bat
) else (
    echo [!] 仮想環境が見つかりません。グローバルPythonを使用します。
)

echo [2/6] 依存関係を確認中...
pip install -r requirements.txt -q

echo [3/6] EXEファイルをビルド中...
pyinstaller --noconfirm millsheet_renamer.spec

echo [4/6] Popplerをダウンロード中...
if not exist "poppler.zip" (
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip' -OutFile 'poppler.zip'"
)

echo [5/6] Popplerを配置中...
powershell -Command "Expand-Archive -Path 'poppler.zip' -DestinationPath 'dist\MillsheetRenamer\' -Force"

echo [6/6] 認証キーをコピー中...
for %%f in (*.json) do (
    if not "%%f"=="package.json" (
        copy "%%f" "dist\MillsheetRenamer\" >nul 2>&1
    )
)

echo.
echo ════════════════════════════════════════════════════════════
echo   ビルド完了！
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
