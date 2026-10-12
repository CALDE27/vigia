<#
  Arranca Vigia completo.

  .\iniciar.ps1                 API + video real, y abre el tablero
  .\iniciar.ps1 -Falsos         API con el guion, sin video ni YOLO (plan B)
  .\iniciar.ps1 -Solo api       solo la API (para levantarla despues de cortarla)
  .\iniciar.ps1 -Solo video     solo el video (para reconectar la camara)
#>
param(
    [string]$Video = "datos\videos\videofinal.mp4",
    [switch]$Falsos,
    [ValidateSet("todo", "api", "video")]
    [string]$Solo = "todo"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$tablero = "http://127.0.0.1:8000/"

if (-not (Test-Path $python)) {
    Write-Host "No encuentro .venv\Scripts\python.exe. Crea el entorno virtual primero." -ForegroundColor Red
    exit 1
}

function Abrir-Ventana($titulo, $comando) {
    $linea = "`$host.UI.RawUI.WindowTitle = '$titulo'; & '$python' $comando"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $linea -WorkingDirectory $PSScriptRoot | Out-Null
}

if ($Falsos) {
    $env:VIGIA_FALSOS = "1"
} else {
    Remove-Item Env:VIGIA_FALSOS -ErrorAction SilentlyContinue
}

if ($Solo -ne "video") {
    Write-Host "Levantando la API..." -ForegroundColor Cyan
    Abrir-Ventana "Vigia - API" "-m uvicorn api.principal:app --port 8000"

    $lista = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-WebRequest $tablero -UseBasicParsing -TimeoutSec 2 | Out-Null
            $lista = $true
            break
        } catch { }
    }
    if (-not $lista) {
        Write-Host "La API no respondio en 20 segundos. Mira la ventana 'Vigia - API'." -ForegroundColor Red
        exit 1
    }
    Write-Host "API lista en $tablero" -ForegroundColor Green
}

if ($Solo -ne "api" -and -not $Falsos) {
    if (-not (Test-Path $Video)) {
        Write-Host "No encuentro el video $Video" -ForegroundColor Red
        exit 1
    }
    Write-Host "Arrancando el servicio de vision..." -ForegroundColor Cyan
    Abrir-Ventana "Vigia - Video" "herramientas\correr_video.py --fuente '$Video'"
}

if ($Solo -eq "todo") { Start-Process $tablero }

Write-Host ""
Write-Host "Listo. Para simular fallas en la demo:" -ForegroundColor Yellow
Write-Host "  Camara cortada: Ctrl+C en la ventana 'Vigia - Video'.  Volver: .\iniciar.ps1 -Solo video"
Write-Host "  API caida:      Ctrl+C en la ventana 'Vigia - API'.    Volver: .\iniciar.ps1 -Solo api"
Write-Host "Para terminar, cerra las dos ventanas."