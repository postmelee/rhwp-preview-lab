// Only public production UI/API surfaces: no dev-only globals or font permission grants.
import {execFileSync} from 'node:child_process';

// Serialized by Puppeteer. A file title changes before initializeDocument finishes.
export function documentReadyOrFontChoice(filename) {
  const dialogs = [...document.querySelectorAll('.modal-overlay .dialog-wrap')]
    .filter(dialog => dialog.getClientRects().length > 0);
  const top = dialogs.at(-1);
  if (top) {
    const title = top.querySelector('.dialog-title')?.firstChild?.textContent.trim();
    if (title === '로컬 글꼴 감지') {
      return [...top.querySelectorAll('.dialog-footer button')]
        .find(button => button.textContent.trim() === '대체 글꼴로 보기' && !button.disabled) || false;
    }
    return false; // Never dismiss an unexpected dialog or click its primary action.
  }
  const context = window.rhwpStudio?.automation?.getContext();
  const canvas = document.querySelector('#scroll-container canvas');
  const status = document.getElementById('sb-message')?.textContent || '';
  return Boolean(context?.hasDocument && !context.isDirty && !context.canUndo
    && !document.documentElement.classList.contains('rhwp-busy')
    && canvas?.getBoundingClientRect().width > 0
    && status.includes(filename) && document.title.includes(filename));
}

export async function waitForDocumentReady(page, filename, {timeout = 60000} = {}) {
  const deadline = Date.now() + timeout;
  let fontPrompts = 0;
  while (Date.now() < deadline) {
    const state = await page.waitForFunction(documentReadyOrFontChoice,
      {timeout: Math.max(1, deadline - Date.now()), polling: 50}, filename);
    try {
      const button = state.asElement();
      if (!button) return {filename, fontPrompts};
      await button.click();
      fontPrompts++;
    } finally {
      await state.dispose();
    }
  }
  throw new Error(`Document did not become ready: ${filename}`);
}

export function saveAsDialog() {
  const dialogs = [...document.querySelectorAll('.modal-overlay .dialog-wrap')]
    .filter(dialog => dialog.getClientRects().length > 0);
  const dialog = dialogs.at(-1);
  return dialog?.querySelector('.dialog-title')?.firstChild?.textContent.trim() === '다른 이름으로 저장'
    && dialog.querySelector('.dialog-body input[type="text"]')
    && dialog.querySelector('.dialog-footer .dialog-btn-primary') ? dialog : false;
}

export async function confirmSaveAs(page, filename, {timeout = 10000} = {}) {
  const handle = await page.waitForFunction(saveAsDialog, {timeout});
  try {
    const dialog = handle.asElement();
    const input = await dialog.$('.dialog-body input[type="text"]');
    await input.evaluate(element => { element.focus(); element.select(); });
    await input.type(filename.replace(/\.hwpx$/i, ''));
    // Keep both controls scoped to the same, identified Save As dialog.
    const confirm = await dialog.$('.dialog-footer .dialog-btn-primary');
    await confirm.click();
  } finally {
    await handle.dispose();
  }
}

export function assertHwpxText(path, markers) {
  execFileSync('python3', ['-c',
    'import sys,zipfile,xml.etree.ElementTree as E; z=zipfile.ZipFile(sys.argv[1]); text="".join("".join(E.fromstring(z.read(n)).itertext()) for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml")); missing=[m for m in sys.argv[2:] if m not in text]; assert not missing,(missing,repr(text))',
    path, ...markers], {stdio: 'pipe'});
}
