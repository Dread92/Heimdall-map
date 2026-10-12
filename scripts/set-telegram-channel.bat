<# : Heimdall - set-telegram-channel.bat
@echo off
rem One-time (1.58): connects your private Telegram channel. The server then posts there one message per target over
rem Kyiv and Kyiv oblast, with a picture of the map around it, and edits it as new reports of the same target come in.
rem ONE file: cmd runs the lines up to "exit /b"; PowerShell reads the whole file, where these lines are a comment.
rem The bot's token is asked here, hidden (one * per character), checked with Telegram, and goes straight into Fly's
rem secret store with the channel's id (TG_BOT_TOKEN, TG_CHANNEL_ID): never into a file, the repository or the chat.
setlocal
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set "HD_SELF=%~f0"
powershell -NoProfile -Command "iex ([IO.File]::ReadAllText($env:HD_SELF))"
pause
exit /b
#>
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$app = 'kyiv-air-watch-gb'
if (Test-Path '.flyapp') { $app = (Get-Content '.flyapp' -TotalCount 1).Trim() }
if (-not (Get-Command fly -ErrorAction SilentlyContinue)) { Write-Host '*** flyctl not found - run deploy-fly.bat once first.' -ForegroundColor Red; return }

Write-Host ''
Write-Host '=== Heimdall - your private Telegram channel ==='
Write-Host ''
Write-Host '1. In Telegram, open @BotFather: /newbot, give it a name (e.g. Heimdall Kyiv) and a username ending in "bot".'
Write-Host '   BotFather answers with a token (123456789:AA...). Keep it to yourself.'
Write-Host '2. Create a channel: New Channel - Private. Name it as you like.'
Write-Host '3. Channel - Administrators - Add Admin - search your bot - allow "Post messages" and "Edit messages of others".'
Write-Host '4. Post any message in the channel (e.g. "test"): that is how the bot learns the channel''s id.'
Write-Host ''

$tok = $null
function Forget { $script:tok = $null; [GC]::Collect() }
function Tg([string]$method, $body) {
  # the token is in the address Telegram asks for: on an error, only the method's name is shown
  try {
    $r = Invoke-RestMethod -Method Post -Uri ("https://api.telegram.org/bot" + $script:tok + "/" + $method) `
      -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 5 -Compress)))
    if ($r.ok) { return $r.result }
  } catch { }
  return $null
}

for ($i = 1; $i -le 3; $i++) {
  $s = Read-Host "Bot token from BotFather (right-click pastes), try $i/3" -AsSecureString
  if ($s.Length -eq 0) { Write-Host 'Nothing entered.' -ForegroundColor Yellow; continue }
  $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
  try { $script:tok = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)).Trim() }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
  $me = Tg 'getMe' @{}
  if ($me) { break }
  Write-Host 'Telegram does not know this token - copy it again from BotFather.' -ForegroundColor Yellow
  Forget
}
if (-not $tok) { Write-Host '*** No valid token - nothing changed.' -ForegroundColor Red; return }
Write-Host ("Bot: @" + $me.username) -ForegroundColor Green

# the channel: from the bot's updates (its addition as an admin, or a post in the channel)
$chan = $null
for ($try = 1; $try -le 5 -and -not $chan; $try++) {
  $ups = Tg 'getUpdates' @{ allowed_updates = @('channel_post', 'my_chat_member'); timeout = 0 }
  $seen = @{}
  foreach ($u in @($ups)) {
    $c = $null
    if ($u.channel_post) { $c = $u.channel_post.chat } elseif ($u.my_chat_member) { $c = $u.my_chat_member.chat }
    if ($c -and $c.type -eq 'channel') { $seen["$($c.id)"] = $c.title }
  }
  if ($seen.Count -eq 1) { $k = @($seen.Keys)[0]; $chan = @{ id = $k; title = $seen[$k] } }
  elseif ($seen.Count -gt 1) {
    $keys = @($seen.Keys)
    for ($j = 0; $j -lt $keys.Count; $j++) { Write-Host ("  " + ($j + 1) + ". " + $seen[$keys[$j]]) }
    $n = Read-Host 'Which channel (number)'
    if ($n -match '^\d+$' -and [int]$n -ge 1 -and [int]$n -le $keys.Count) { $k = $keys[[int]$n - 1]; $chan = @{ id = $k; title = $seen[$k] } }
  } else {
    Write-Host 'The bot sees no channel yet: add it as an administrator, post a message in the channel, then press Enter.' -ForegroundColor Yellow
    [void](Read-Host)
  }
}
if (-not $chan) { Forget; Write-Host '*** No channel found - nothing changed.' -ForegroundColor Red; return }
Write-Host ("Channel: " + $chan.title + "  (id " + $chan.id + ")") -ForegroundColor Green

$m = Tg 'getChatMember' @{ chat_id = $chan.id; user_id = $me.id }
if (-not $m -or $m.status -ne 'administrator' -or -not $m.can_post_messages -or -not $m.can_edit_messages) {
  Write-Host 'The bot must be an administrator of the channel with "Post messages" and "Edit messages of others".' -ForegroundColor Yellow
  Write-Host 'Fix it in the channel''s Administrators, then run this script again.' -ForegroundColor Yellow
  Forget; return
}

$go = Read-Host ("Connect Heimdall to """ + $chan.title + """ (Y/n)")
if ($go -match '^[nN]') { Forget; Write-Host 'Nothing changed.'; return }
$t = Tg 'sendMessage' @{ chat_id = $chan.id; text = "Heimdall: канал підключено. Тут з'являтимуться цілі над Києвом і Київщиною - з дописів каналів, не радар." }
if (-not $t) { Write-Host 'The test message could not be posted - check the bot''s rights.' -ForegroundColor Yellow; Forget; return }

# into Fly's secret store, through the input of "fly secrets import": never on the command line, never in a file
("TG_BOT_TOKEN=" + $tok + "`nTG_CHANNEL_ID=" + $chan.id) | fly secrets import -a $app
$rc = $LASTEXITCODE
Forget
if ($rc -ne 0) { Write-Host '*** fly could not store the secrets - nothing changed.' -ForegroundColor Red; return }
Write-Host ''
Write-Host 'Done. Fly restarts the app; the dashboard (Health - official sources) shows "telegram channel (posting)".' -ForegroundColor Green
Write-Host 'To stop the channel: fly secrets unset TG_BOT_TOKEN TG_CHANNEL_ID -a' $app
