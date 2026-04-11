$root = $PSScriptRoot
$port = 3000
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://127.0.0.1:$port/")
$listener.Start()
Write-Host "Serving $root at http://127.0.0.1:$port/"
function Get-Mime([string]$path) {
    switch -Regex ($path) {
        '\.html$' { return 'text/html; charset=utf-8' }
        '\.css$' { return 'text/css' }
        '\.js$' { return 'application/javascript' }
        '\.svg$' { return 'image/svg+xml' }
        '\.(webmanifest|json)$' { return 'application/json' }
        '\.(png|jpg|jpeg|gif|webp|ico)$' { return 'image/' + ($path -replace '.*\.', '') }
        default { return 'application/octet-stream' }
    }
}
try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        $req = $ctx.Request
        $res = $ctx.Response
        $path = [Uri]::UnescapeDataString($req.Url.AbsolutePath.TrimStart('/'))
        if ([string]::IsNullOrEmpty($path)) { $path = 'index.html' }
        $file = Join-Path $root $path
        if (-not (Test-Path $file -PathType Leaf)) {
            $res.StatusCode = 404
            $buf = [Text.Encoding]::UTF8.GetBytes('404 Not Found')
            $res.ContentLength64 = $buf.Length
            $res.OutputStream.Write($buf, 0, $buf.Length)
        } else {
            $bytes = [System.IO.File]::ReadAllBytes($file)
            $res.ContentType = Get-Mime $file
            $res.ContentLength64 = $bytes.Length
            $res.OutputStream.Write($bytes, 0, $bytes.Length)
        }
        $res.Close()
    }
} finally {
    $listener.Stop()
}
