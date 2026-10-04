param([string]$Carpeta, [switch]$Restaurar, [switch]$SinVentana,
      [string]$RaizRespaldos)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$script:Paquete = $PSScriptRoot

function Hash-Bytes([byte[]]$Datos) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($Datos))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
}
function Hash-File([string]$Ruta) {
    $stream = [IO.File]::OpenRead($Ruta); $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $hash.Dispose() }
}
function Leer-Entrada($Entrada) {
    $stream = $Entrada.Open(); $memory = New-Object IO.MemoryStream
    try { $stream.CopyTo($memory); return ,$memory.ToArray() }
    finally { $stream.Dispose(); $memory.Dispose() }
}
function Aplicar-Diferencia([byte[]]$Original, $Entrada) {
    $memory = New-Object IO.MemoryStream
    try {
        foreach ($op in $Entrada.operaciones) {
            if ($op -is [string]) {
                $bytes = [Convert]::FromBase64String($op)
                $memory.Write($bytes, 0, $bytes.Length)
            } else {
                $offset = [int]$op[0]; $length = [int]$op[1]
                if ($offset -lt 0 -or $length -lt 0 -or $offset + $length -gt $Original.Length) {
                    throw 'Diferencia fuera de los limites del original.'
                }
                $memory.Write($Original, $offset, $length)
            }
        }
        $result = $memory.ToArray()
        if ($result.Length -ne $Entrada.longitud -or (Hash-Bytes $result) -ne $Entrada.traducido) {
            throw "Parche danado: $($Entrada.nombre)"
        }
        return ,$result
    } finally { $memory.Dispose() }
}
function Comprobar-Cerrado([string]$Juego) {
    # En Windows, el lanzador Java puede tener un nombre generico.
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $processes = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%java%' OR Name LIKE '%LostFlame%'" -ErrorAction Stop)
        foreach ($p in $processes) {
            if ($p.Name -like '*LostFlame*' -or $p.CommandLine -like '*LostFlame.jar*' -or
                ($p.ExecutablePath -and $p.ExecutablePath.StartsWith($Juego, [StringComparison]::OrdinalIgnoreCase))) {
                throw 'Cierra Lost Flame antes de continuar.'
            }
        }
    }
    # Acceso exclusivo: tambien evita editar un JAR abierto por otra aplicacion.
    $stream = [IO.File]::Open((Join-Path $Juego 'LostFlame.jar'), 'Open', 'Read', 'None')
    $stream.Dispose()
}
function Ruta-Respaldo([string]$Juego) {
    $root = $RaizRespaldos
    if (-not $root) { $root = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'LostFlameES/respaldos' }
    $key = Hash-Bytes ([Text.Encoding]::UTF8.GetBytes($Juego.ToLowerInvariant()))
    return Join-Path $root $key.Substring(0,24)
}
function Cambios($Jar, $Parche) {
    $updates = @{}; $translated = 0; $seen = @{}
    foreach ($e in $Jar.Entries) {
        if ($seen.ContainsKey($e.FullName)) { throw 'El archivo contiene entradas duplicadas.' }
        $seen[$e.FullName] = $true
    }
    foreach ($e in $Parche.entradas) {
        $source = $Jar.GetEntry($e.nombre)
        $old = [byte[]]@(); $current = $null
        if ($source) { $old = Leer-Entrada $source; $current = Hash-Bytes $old }
        if ($current -eq $e.traducido) { $translated++ }
        elseif ($current -eq $e.original) { $updates[$e.nombre] = Aplicar-Diferencia $old $e }
        else { throw "Version incompatible o modificada: $($e.nombre). No se ha cambiado el juego." }
    }
    if ($translated -gt 0 -and $updates.Count -gt 0) {
        throw 'Instalacion parcialmente modificada. Restaura o verifica los archivos con Steam.'
    }
    return $updates
}
function Instalar-Traduccion([string]$Juego) {
    $Juego = (Resolve-Path -LiteralPath $Juego).Path.TrimEnd([IO.Path]::DirectorySeparatorChar)
    Comprobar-Cerrado $Juego
    $jarPath = Join-Path $Juego 'LostFlame.jar'
    $patch = Get-Content -LiteralPath (Join-Path $script:Paquete 'parche/parche.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $source = [IO.Compression.ZipFile]::OpenRead($jarPath)
    $temp = Join-Path $Juego ('.lost-flame-es-' + [Guid]::NewGuid().ToString('N') + '.jar')
    try {
        $updates = Cambios $source $patch
        if ($updates.Count -eq 0) { return 'Esta traduccion ya esta instalada.' }
        $before = Hash-File $jarPath
        $backup = Ruta-Respaldo $Juego
        [IO.Directory]::CreateDirectory($backup) | Out-Null
        $original = Join-Path $backup ([Guid]::NewGuid().ToString('N') + '.jar')
        [IO.File]::Copy($jarPath, $original, $false)
        if ((Hash-File $original) -ne $before) { throw 'La copia de seguridad no coincide con el juego.' }
        $target = [IO.Compression.ZipFile]::Open($temp, [IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($e in $source.Entries) {
                $dest = $target.CreateEntry($e.FullName, [IO.Compression.CompressionLevel]::Optimal)
                $dest.LastWriteTime = $e.LastWriteTime
                $out = $dest.Open()
                try {
                    if ($updates.ContainsKey($e.FullName)) {
                        $bytes = $updates[$e.FullName]; $out.Write($bytes, 0, $bytes.Length)
                    } else {
                        $in = $e.Open(); try { $in.CopyTo($out) } finally { $in.Dispose() }
                    }
                } finally { $out.Dispose() }
            }
            foreach ($name in $updates.Keys) {
                if (-not $source.GetEntry($name)) {
                    $dest = $target.CreateEntry($name); $out = $dest.Open()
                    try { $bytes = $updates[$name]; $out.Write($bytes, 0, $bytes.Length) }
                    finally { $out.Dispose() }
                }
            }
        } finally { $target.Dispose() }
        $check = [IO.Compression.ZipFile]::OpenRead($temp)
        try { if ((Cambios $check $patch).Count -ne 0) { throw 'No se pudo validar el parche.' } }
        finally { $check.Dispose() }
        $after = Hash-File $temp
        $state = @{original=[IO.Path]::GetFileName($original); sha_original=$before; sha_instalado=$after}
        $pending = Join-Path $backup ('estado-' + [Guid]::NewGuid().ToString('N') + '.json')
        $state | ConvertTo-Json | Set-Content -LiteralPath $pending -Encoding UTF8
        $source.Dispose(); $source = $null
        Comprobar-Cerrado $Juego
        if ((Hash-File $jarPath) -ne $before) { throw 'El juego cambio durante la instalacion.' }
        $committed = $false
        try {
            [IO.File]::Replace($temp, $jarPath, [System.Management.Automation.Language.NullString]::Value)
            $committed = $true
            $statePath = Join-Path $backup 'estado.json'
            if (Test-Path -LiteralPath $statePath) { [IO.File]::Replace($pending, $statePath, [System.Management.Automation.Language.NullString]::Value) }
            else { [IO.File]::Move($pending, $statePath) }
        } catch {
            if ($committed) {
                [IO.File]::Copy($original, $temp, $false)
                [IO.File]::Replace($temp, $jarPath, [System.Management.Automation.Language.NullString]::Value)
            }
            throw
        }
        return "Traduccion instalada. Respaldo: $backup"
    } finally {
        if ($source) { $source.Dispose() }
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    }
}
function Restaurar-Juego([string]$Juego) {
    $Juego = (Resolve-Path -LiteralPath $Juego).Path.TrimEnd([IO.Path]::DirectorySeparatorChar)
    Comprobar-Cerrado $Juego
    $backup = Ruta-Respaldo $Juego
    $statePath = Join-Path $backup 'estado.json'
    if (-not (Test-Path -LiteralPath $statePath)) { throw 'No se encontro un respaldo para esta carpeta.' }
    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $jar = Join-Path $Juego 'LostFlame.jar'; $original = Join-Path $backup $state.original
    if ((Hash-File $jar) -ne $state.sha_instalado) {
        throw 'Steam u otro programa cambio el juego. Se conserva el respaldo y no se sobrescribe esta version.'
    }
    if ((Hash-File $original) -ne $state.sha_original) { throw 'El respaldo esta danado.' }
    $temp = Join-Path $Juego ('.lost-flame-es-' + [Guid]::NewGuid().ToString('N') + '.jar')
    try {
        [IO.File]::Copy($original, $temp, $false)
        Comprobar-Cerrado $Juego
        if ((Hash-File $jar) -ne $state.sha_instalado) { throw 'El juego cambio durante la restauracion.' }
        [IO.File]::Replace($temp, $jar, [System.Management.Automation.Language.NullString]::Value)
        Remove-Item -LiteralPath $statePath
        return 'Juego original restaurado. La copia de seguridad se conserva.'
    } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
}
function Buscar-Juegos {
    $roots = @()
    foreach ($key in @('HKCU:\Software\Valve\Steam','HKLM:\SOFTWARE\WOW6432Node\Valve\Steam')) {
        $value = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
        if ($value.SteamPath) { $roots += $value.SteamPath }
        if ($value.InstallPath) { $roots += $value.InstallPath }
    }
    if (${env:ProgramFiles(x86)}) { $roots += Join-Path ${env:ProgramFiles(x86)} 'Steam' }
    $libraries = @($roots)
    foreach ($root in $roots) {
        $vdf = Join-Path $root 'steamapps/libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            $text = Get-Content -LiteralPath $vdf -Raw
            foreach ($m in [regex]::Matches($text, '"path"\s*"([^"]+)"')) {
                $libraries += $m.Groups[1].Value.Replace('\\','\')
            }
        }
    }
    return @($libraries | Select-Object -Unique | ForEach-Object {
        $game = Join-Path $_ 'steamapps/common/Lost Flame'
        if (Test-Path -LiteralPath (Join-Path $game 'LostFlame.jar')) { $game }
    })
}

if ($SinVentana) {
    if (-not $Carpeta) { throw 'Indica -Carpeta para usar el modo sin ventana.' }
    if ($Restaurar) { Restaurar-Juego $Carpeta } else { Instalar-Traduccion $Carpeta }
    exit
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form
$form.Text = 'Lost Flame en español'; $form.Size = New-Object Drawing.Size(640,245)
$form.StartPosition = 'CenterScreen'; $form.FormBorderStyle = 'FixedDialog'; $form.MaximizeBox = $false
$label = New-Object Windows.Forms.Label
$label.Text = 'Cierra el juego. Selecciona su carpeta para instalar o restaurar la traducción.'
$label.SetBounds(20,18,595,35)
$path = New-Object Windows.Forms.TextBox; $path.SetBounds(20,60,475,25)
$games = @(Buscar-Juegos)
if ($Carpeta) { $path.Text = $Carpeta } elseif ($games.Count -gt 0) { $path.Text = $games[0] }
$browse = New-Object Windows.Forms.Button; $browse.Text = 'Buscar…'; $browse.SetBounds(505,58,105,29)
$browse.Add_Click({
    $dialog = New-Object Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Selecciona la carpeta Lost Flame, donde está LostFlame.jar.'
    if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) { $path.Text = $dialog.SelectedPath }
    $dialog.Dispose()
})
$install = New-Object Windows.Forms.Button; $install.Text = 'Instalar traducción'; $install.SetBounds(20,106,185,36)
$restore = New-Object Windows.Forms.Button; $restore.Text = 'Restaurar original'; $restore.SetBounds(220,106,185,36)
$status = New-Object Windows.Forms.Label; $status.Text = 'El respaldo se guarda fuera de la carpeta de Steam.'; $status.SetBounds(20,158,595,35)
$install.Add_Click({
    $install.Enabled = $false; $restore.Enabled = $false; $status.Text = 'Instalando…'; $form.Refresh()
    try { $message = Instalar-Traduccion $path.Text; [Windows.Forms.MessageBox]::Show($message, 'Lost Flame') | Out-Null; $status.Text = 'Traducción instalada.' }
    catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'No se pudo instalar') | Out-Null; $status.Text = 'Revisa el aviso y vuelve a intentarlo.' }
    finally { $install.Enabled = $true; $restore.Enabled = $true }
})
$restore.Add_Click({
    $install.Enabled = $false; $restore.Enabled = $false; $status.Text = 'Restaurando…'; $form.Refresh()
    try { $message = Restaurar-Juego $path.Text; [Windows.Forms.MessageBox]::Show($message, 'Lost Flame') | Out-Null; $status.Text = 'Original restaurado.' }
    catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'No se pudo restaurar') | Out-Null; $status.Text = 'Revisa el aviso y vuelve a intentarlo.' }
    finally { $install.Enabled = $true; $restore.Enabled = $true }
})
$form.Controls.AddRange(@($label,$path,$browse,$install,$restore,$status))
[void]$form.ShowDialog(); $form.Dispose()
