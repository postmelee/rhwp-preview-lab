// Public read-only status query; no token or server-side code is needed.
const label = document.getElementById('preview-freshness');
try {
  const upstream = await fetch('https://api.github.com/repos/edwardkim/rhwp/commits/devel', {signal: AbortSignal.timeout(8000)});
  if (!upstream.ok) throw new Error('Status unavailable');
  const current = await upstream.json();
  const displayedSHA = document.getElementById('devel-preview-status').dataset.sourceSha;
  if (!/^[a-f0-9]{40}$/.test(current.sha)) throw new Error('Invalid SHA');
  label.textContent = displayedSHA === current.sha ? '조회 시점 최신 devel' : `갱신 대기 (최신 ${current.sha.slice(0, 12)})`;
} catch {
  label.textContent = '최신 여부 확인 불가';
}
