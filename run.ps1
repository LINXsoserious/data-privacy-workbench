param(
    [string]$PythonPath = "",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
Push-Location -LiteralPath $PSScriptRoot
try {
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            throw "The specified Python executable does not exist."
        }
        $privacyPython = (Resolve-Path -LiteralPath $PythonPath).Path
    } else {
        $privacyPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $privacyPython)) {
            & python -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw "Unable to create the virtual environment." }
            & $privacyPython -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
        }
    }
    & $privacyPython -m streamlit run app.py --server.address 127.0.0.1 --server.port $Port --browser.gatherUsageStats false
    if ($LASTEXITCODE -ne 0) { throw "Streamlit stopped with an error." }
} finally {
    Pop-Location
}
