// Time belongs to this loaded build; ticking does not fetch or reload anything.
function relativeBuildTime(iso, now = Date.now()) {
  const built = Date.parse(iso);
  if (!Number.isFinite(built)) return '빌드 시각 확인 불가';
  const seconds = Math.max(0, (now - built) / 1000);
  if (seconds < 60) return 'Built just now';
  const [unit, divisor] = seconds < 3600 ? ['minute', 60]
    : seconds < 86400 ? ['hour', 3600] : ['day', 86400];
  return `Built ${new Intl.RelativeTimeFormat('en', {numeric: 'always'}).format(-Math.floor(seconds / divisor), unit)}`;
}

function startBuildClock() {
  const timestamp = document.getElementById('preview-built-at');
  const label = document.getElementById('preview-relative-time');
  if (!timestamp || !label) return;
  const builtAt = timestamp.dateTime;
  const update = () => { label.textContent = relativeBuildTime(builtAt); };
  update();
  setInterval(update, 30000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) update();
  });
}

// Check once per page load; the local build clock never refreshes this result.
async function checkFreshness() {
  const label = document.getElementById('preview-freshness');
  try {
    const upstream = await fetch('https://api.github.com/repos/edwardkim/rhwp/git/ref/heads/devel', {signal: AbortSignal.timeout(8000)});
    if (!upstream.ok) throw new Error('Status unavailable');
    const current = (await upstream.json()).object;
    const displayedSHA = document.getElementById('devel-preview-status').dataset.sourceSha;
    if (!/^[a-f0-9]{40}$/.test(current.sha)) throw new Error('Invalid SHA');
    const checkedAt = new Intl.DateTimeFormat('sv-SE', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }).format(Date.now());
    label.textContent = displayedSHA === current.sha ? '최신 devel 반영됨' : '최신 devel 미반영';
    label.title = `확인 시각: ${checkedAt} KST\n최신 devel SHA: ${current.sha}`;
  } catch {
    label.textContent = '최신 devel 확인 불가';
    label.title = '최신 devel 정보를 가져오지 못했습니다. 새로고침하여 다시 확인하세요.';
  }
}

startBuildClock();
void checkFreshness();
