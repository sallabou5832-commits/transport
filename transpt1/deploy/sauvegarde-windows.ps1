# Sauvegarde de la base sous Windows — à planifier avec le Planificateur de tâches (voir DEPLOIEMENT.md §3) :
#
#   schtasks /Create /TN "Transport Coord - sauvegarde" /SC DAILY /ST 02:30 /RU SYSTEM `
#       /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\transport\transpt1\deploy\sauvegarde-windows.ps1"
#
# Les variables (DB_*, BACKUP_DIR…) sont lues dans le .env du projet par Django ; ce script ne contient aucun secret.
# Sortie en erreur (code 1) si la sauvegarde ou son envoi échoue : la tâche apparaît « en échec » dans le planificateur.
$ErrorActionPreference = 'Stop'
$projet = Split-Path -Parent $PSScriptRoot
Set-Location $projet

$python = Join-Path (Split-Path -Parent $projet) 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = Join-Path $projet 'venv\Scripts\python.exe' }

& $python manage.py sauvegarde_base
exit $LASTEXITCODE
