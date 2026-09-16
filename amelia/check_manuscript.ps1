$ErrorActionPreference = 'Stop'
$ameliaRoot = $PSScriptRoot
$ameliaState = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path $ameliaRoot 'state.json') | ConvertFrom-Json
$ameliaBlocked = @('扇','七つ数え','7つ数え','イレーネ','タケシ','灰の都','灰猫亭','三本釘','石角詰所','緑紐','折れ灯','Skjól','Heilsa','Ljósflæði','Hreinsun','Umbreyta','TODO','TBD','{{file:')
$ameliaReports = @()
$ameliaIds = @($ameliaState.cards | ForEach-Object { $_.id })
if (($ameliaIds | Select-Object -Unique).Count -ne $ameliaIds.Count) { throw '重複カードIDがあります。' }
foreach ($ameliaScene in $ameliaState.scene_log) {
    if (-not $ameliaScene.path) { continue }
    $ameliaPath = Join-Path $ameliaRoot $ameliaScene.path
    if (-not (Test-Path -LiteralPath $ameliaPath -PathType Leaf)) { throw "本文がありません: $($ameliaScene.id)" }
    $ameliaText = Get-Content -Raw -Encoding utf8 -LiteralPath $ameliaPath
    $ameliaBody = (($ameliaText -split '\r?\n') | Where-Object { $_ -notmatch '^#' }) -join "`n"
    $ameliaHits = @($ameliaBlocked | Where-Object { $ameliaBody.Contains($_) })
    foreach ($ameliaPerson in $ameliaScene.participants) {
        if ($ameliaPerson -notin $ameliaIds) { throw "人物カードがありません: $ameliaPerson" }
    }
    if ($ameliaScene.location -notin $ameliaIds) { throw "場所カードがありません: $($ameliaScene.location)" }
    $ameliaCount = ($ameliaBody -replace '\s','').Length
    $ameliaReports += [pscustomobject]@{
        scene = $ameliaScene.id
        status = $ameliaScene.status
        characters_excluding_whitespace_and_headings = $ameliaCount
        blocked_terms = $ameliaHits
        structural_check = '本文、参加者、場所の参照を確認'
    }
}
$ameliaReport = [pscustomobject]@{
    checked_at = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')
    reports = $ameliaReports
    limitation = '文字列と参照の検査のみ。心理・歴史・因果・完成品質は別途読解が必要。'
}
$ameliaReport | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $ameliaRoot 'check_report.json')
$ameliaReport | ConvertTo-Json -Depth 10
if (@($ameliaReports | Where-Object { $_.blocked_terms.Count -gt 0 }).Count -gt 0) { throw '本文に確認対象語があります。' }
