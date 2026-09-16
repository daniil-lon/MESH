$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = "py"
& $py -3 -m pip install --quiet pyinstaller pywebview pillow
if (-not $?) { throw "pip install failed" }

$stage = Join-Path $env:TEMP "mesh_build_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

robocopy "$root\backend" "$stage\backend" /E /XD versions __pycache__ /XF "*.pyc" /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy "$root\css" "$stage\css" /E /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy "$root\js" "$stage\js" /E /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy "$root\icons" "$stage\icons" /E /NFL /NDL /NJH /NJS /NP | Out-Null
Copy-Item "$root\index.html", "$root\admin.html", "$root\manifest.json", "$root\sw.js" $stage -Force
New-Item -ItemType Directory -Path "$stage\uploads" -Force | Out-Null

$ico = Join-Path $stage "icon.ico"
& $py -3 -c "from PIL import Image; im=Image.open(r'icons\icon-512.png').convert('RGBA'); im.thumbnail((256,256)); im.save(r'$ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
if (-not (Test-Path $ico)) { throw "icon conversion failed" }

& $py -3 -m PyInstaller --noconfirm --onefile --windowed --name "MeshCollegeApp" `
  --icon $ico `
  --add-data "$stage\backend;backend" `
  --add-data "$stage\css;css" `
  --add-data "$stage\js;js" `
  --add-data "$stage\icons;icons" `
  --add-data "$stage\uploads;uploads" `
  --add-data "$stage\index.html;." `
  --add-data "$stage\admin.html;." `
  --add-data "$stage\manifest.json;." `
  --add-data "$stage\sw.js;." `
  desktop_app.py
if (-not $?) { throw "PyInstaller failed" }

Write-Host "BUILD OK: $root\dist\MeshCollegeApp.exe"