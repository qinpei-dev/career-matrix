// Draggable floating CareerMatrix window shown on top of the current page.
//
// Injected by the background worker when the user clicks the toolbar icon (or
// presses Alt+J), and loaded on www.zhipin.com so the window reopens by itself
// after the page reloads. The window is an iframe of the extension's own page;
// the host page cannot read or script it.
(() => {
  if (window.__careerMatrixFloating) return;

  const STATE_KEY = "floatingWindow";
  const WIDTH = 440;
  const HEIGHT = 640;
  let host = null;

  const clamp = (value, max) => Math.max(0, Math.min(value, Math.max(0, max)));

  async function saveState(patch) {
    const { [STATE_KEY]: state } = await chrome.storage.local.get({ [STATE_KEY]: {} });
    await chrome.storage.local.set({ [STATE_KEY]: { ...state, ...patch } });
  }

  async function show() {
    if (host) return;
    const { [STATE_KEY]: state } = await chrome.storage.local.get({ [STATE_KEY]: {} });
    if (host) return;
    // Reloading the extension leaves the old window on the page, cut off from
    // the new code. Keep exactly one window: drop any left-over ones.
    document.querySelectorAll("#careermatrix-floating-host").forEach((old) => old.remove());

    host = document.createElement("div");
    host.id = "careermatrix-floating-host";
    const shadow = host.attachShadow({ mode: "closed" });
    shadow.innerHTML = `
      <style>
        .window {
          position: fixed;
          z-index: 2147483647;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          width: ${WIDTH}px;
          height: ${HEIGHT}px;
          min-width: 320px;
          min-height: 240px;
          max-width: 100vw;
          max-height: 100vh;
          overflow: hidden;
          resize: both;
          border: 1px solid #d0d7de;
          border-radius: 10px;
          background: #fff;
          box-shadow: 0 12px 32px rgba(0, 0, 0, 0.22);
          font: 13px/1.4 system-ui, "Microsoft YaHei", sans-serif;
        }
        .bar {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 8px 6px 12px;
          background: #1f2937;
          color: #fff;
          cursor: move;
          user-select: none;
          touch-action: none;
        }
        .title { flex: 1; font-weight: 600; }
        button {
          border: 0;
          border-radius: 6px;
          padding: 2px 8px;
          background: transparent;
          color: inherit;
          font: inherit;
          cursor: pointer;
        }
        button:hover { background: rgba(255, 255, 255, 0.15); }
        iframe { flex: 1; width: 100%; border: 0; background: #fff; }
        .collapsed { height: auto !important; min-height: 0; resize: none; }
        .collapsed iframe { display: none; }
      </style>
      <div class="window">
        <div class="bar" title="拖动这里移动窗口">
          <span class="title">CareerMatrix</span>
          <button class="collapse" type="button" title="收起 / 展开">—</button>
          <button class="close" type="button" title="关闭">✕</button>
        </div>
        <iframe title="CareerMatrix" allow="clipboard-write"></iframe>
      </div>`;

    const win = shadow.querySelector(".window");
    const bar = shadow.querySelector(".bar");
    const frame = shadow.querySelector("iframe");
    frame.src = chrome.runtime.getURL("popup.html");
    win.style.left = `${clamp(state.left ?? window.innerWidth - WIDTH - 24, window.innerWidth - 120)}px`;
    win.style.top = `${clamp(state.top ?? 24, window.innerHeight - 40)}px`;
    if (state.width) win.style.width = `${state.width}px`;
    if (state.height) win.style.height = `${state.height}px`;
    if (state.collapsed) win.classList.add("collapsed");

    // Drag by the title bar. Pointer capture keeps the drag going while the
    // cursor passes over the iframe.
    let drag = null;
    bar.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("button")) return;
      const rect = win.getBoundingClientRect();
      drag = { dx: event.clientX - rect.left, dy: event.clientY - rect.top };
      bar.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    bar.addEventListener("pointermove", (event) => {
      if (!drag) return;
      win.style.left = `${clamp(event.clientX - drag.dx, window.innerWidth - 120)}px`;
      win.style.top = `${clamp(event.clientY - drag.dy, window.innerHeight - 40)}px`;
    });
    bar.addEventListener("pointerup", () => {
      if (!drag) return;
      drag = null;
      saveState({ left: parseInt(win.style.left, 10), top: parseInt(win.style.top, 10) });
    });

    // Remember the size after the user resizes from the bottom-right corner.
    let resizeTimer;
    new ResizeObserver(() => {
      if (win.classList.contains("collapsed")) return;
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        saveState({ width: win.offsetWidth, height: win.offsetHeight });
      }, 400);
    }).observe(win);

    shadow.querySelector(".collapse").addEventListener("click", () => {
      saveState({ collapsed: win.classList.toggle("collapsed") });
    });
    shadow.querySelector(".close").addEventListener("click", () => hide());

    document.documentElement.append(host);
    saveState({ open: true });
  }

  function hide() {
    host?.remove();
    host = null;
    saveState({ open: false });
  }

  window.__careerMatrixFloating = {
    // A left-over window from before an extension reload counts as closed:
    // show() replaces it with a working one.
    toggle: () => (host ? hide() : show()),
  };

  // Reopen after a reload on the job site if the user left the window open.
  if (location.hostname === "www.zhipin.com") {
    chrome.storage.local.get({ [STATE_KEY]: {} }).then(({ [STATE_KEY]: state }) => {
      if (state.open) show();
    });
  }
})();
