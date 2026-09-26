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

// Public read-only freshness check; separate from the local clock and no token.
async function checkFreshness() {
  const label = document.getElementById('preview-freshness');
  try {
    const upstream = await fetch('https://api.github.com/repos/edwardkim/rhwp/git/ref/heads/devel', {signal: AbortSignal.timeout(8000)});
    if (!upstream.ok) throw new Error('Status unavailable');
    const current = (await upstream.json()).object;
    const displayedSHA = document.getElementById('devel-preview-status').dataset.sourceSha;
    if (!/^[a-f0-9]{40}$/.test(current.sha)) throw new Error('Invalid SHA');
    label.textContent = displayedSHA === current.sha ? '조회 시점 최신 devel' : `현재 화면에 새 devel이 아직 반영되지 않음 (최신 ${current.sha.slice(0, 12)})`;
  } catch {
    label.textContent = '최신 여부 확인 불가';
  }
}

startBuildClock();
void checkFreshness();
