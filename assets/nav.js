(function () {
  "use strict";

  const sidebar = document.querySelector(".docs-sidebar");
  if (!sidebar) return;

  const storageKey = "makoto.docsSidebarScrollTop";
  const save = () => {
    try {
      window.sessionStorage.setItem(storageKey, String(sidebar.scrollTop));
    } catch (_) {
      // Navigation remains usable when storage is disabled.
    }
  };

  try {
    const stored = Number(window.sessionStorage.getItem(storageKey));
    if (Number.isFinite(stored) && stored >= 0) {
      window.requestAnimationFrame(() => {
        sidebar.scrollTop = stored;
      });
    }
  } catch (_) {
    // Navigation remains usable when storage is disabled.
  }

  let frame = 0;
  sidebar.addEventListener(
    "scroll",
    () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        save();
      });
    },
    { passive: true },
  );
  sidebar.addEventListener("click", save);
  window.addEventListener("pagehide", save);
})();
