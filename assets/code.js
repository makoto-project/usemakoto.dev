/*
 * Exhibit frames for every code block: a tab with the filename or language,
 * a copy control, and a terminal treatment for shell sessions.
 *
 * Load order matters. This script is deferred directly after /assets/prism.js,
 * so it runs after Prism registers its languages but before Prism's own
 * DOMContentLoaded highlightAll. That window is where the terminal grammars
 * are registered and shell blocks are re-classed, so Prism highlights them
 * with the right grammar on its single pass. Without Prism (pages with plain
 * <pre> only) the frames and copy controls still work.
 *
 * The text inside each <pre> is never rewritten: what is displayed and what
 * is copied are the published bytes.
 */
(function () {
  "use strict";

  var LABELS = {
    yaml: "yaml", json: "json", python: "python", javascript: "javascript",
    typescript: "typescript", go: "go", sql: "sql", bash: "shell",
    terminal: "terminal", "shell-plain": "shell", none: "text", markup: "html"
  };

  function registerGrammars(Prism) {
    if (!Prism || !Prism.languages || !Prism.languages.bash) return;
    var verdicts = {
      "status-fail": {
        pattern: /^(?:FAIL|DENY|REFUSED|invalid)\b.*$/m,
        inside: {
          "verdict-deny": /^(?:DENY|REFUSED)\b/,
          verdict: /^\S+/,
          "error-code": /\bE_[A-Z0-9_]{3,}\b/
        }
      },
      "status-ok": {
        pattern: /^(?:PASS|ALLOW|ALLOWED)\b.*$/m,
        inside: {
          "verdict-allow": /^(?:ALLOW|ALLOWED)\b/,
          verdict: /^\S+/
        }
      },
      "error-code": /\bE_[A-Z0-9_]{3,}\b/,
      digest: /\bsha256:[0-9a-f]{12,}\b/
    };
    // A session transcript: "$ " lines are commands (with backslash
    // continuations); everything else is captured output.
    Prism.languages.terminal = Object.assign({
      command: {
        pattern: /^\$ .*(?:\\\r?\n.*)*/m,
        inside: Object.assign({ prompt: /^\$/ }, Prism.languages.bash)
      }
    }, verdicts);
    // Commands or output without prompts: shell highlighting, plus verdicts.
    Prism.languages["shell-plain"] = Object.assign({}, verdicts, Prism.languages.bash);
    // GitHub Actions expressions read as their own thing inside workflow YAML.
    if (Prism.languages.yaml) {
      Prism.languages.insertBefore("yaml", "comment", {
        "gha-expression": /\$\{\{[^}]*\}\}/
      });
    }
  }

  function languageOf(code) {
    var match = /(?:^|\s)language-([\w-]+)/.exec(code.className || "");
    return match ? match[1] : "none";
  }

  function isTranscript(text) {
    return /^\$ /m.test(text);
  }

  function copyText(pre, lang) {
    var text = pre.textContent.replace(/\n$/, "");
    if (lang !== "terminal") return text;
    // Copy the commands, not the captured output, with continuations intact.
    var lines = text.split("\n"), out = [], inCommand = false;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (/^\$ /.test(line)) { out.push(line.slice(2)); inCommand = /\\$/.test(line); }
      else if (inCommand) { out.push(line); inCommand = /\\$/.test(line); }
    }
    return out.join("\n");
  }

  var COPY_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-.5A1.5 1.5 0 0 0 9 1.5H3A1.5 1.5 0 0 0 1.5 3v6A1.5 1.5 0 0 0 3 10.5h.5"/></svg>';

  function writeClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(area);
      if (ok) { resolve(); } else { reject(new Error("copy failed")); }
    });
  }

  function frame(pre) {
    if (pre.closest(".exhibit") || pre.dataset.exhibit === "off") return;
    var code = pre.querySelector("code") || pre;
    var lang = languageOf(code);
    if (lang === "none") lang = languageOf(pre);
    var text = pre.textContent;

    if (lang === "bash") {
      lang = isTranscript(text) ? "terminal" : "shell-plain";
      code.className = code.className.replace(/(^|\s)language-bash(?=\s|$)/, "$1language-" + lang);
      pre.className = pre.className.replace(/(^|\s)language-bash(?=\s|$)/, "$1language-" + lang);
    }
    var terminal = lang === "terminal" || lang === "shell-plain";

    var wrap = document.createElement("div");
    wrap.className = "exhibit" + (terminal ? " is-terminal" : "");
    wrap.dataset.lang = lang;

    var head = document.createElement("div");
    head.className = "exhibit-head";

    var dots = document.createElement("span");
    dots.className = "exhibit-dots";
    dots.setAttribute("aria-hidden", "true");
    dots.innerHTML = "<i></i><i></i><i></i>";
    head.appendChild(dots);

    var filename = pre.dataset.filename || code.dataset.filename;
    if (filename) {
      var name = document.createElement("span");
      name.className = "exhibit-name";
      name.textContent = filename;
      name.title = filename;
      head.appendChild(name);
    }

    var label = document.createElement("span");
    label.className = "exhibit-lang";
    label.textContent = LABELS[lang] || lang;
    head.appendChild(label);

    var spacer = document.createElement("span");
    spacer.className = "exhibit-spacer";
    head.appendChild(spacer);

    var button = document.createElement("button");
    button.type = "button";
    button.className = "exhibit-copy";
    var idle = lang === "terminal" ? "Copy commands" : "Copy";
    button.innerHTML = COPY_ICON + "<span>" + idle + "</span>";
    button.setAttribute("aria-label", idle + (filename ? " from " + filename : ""));
    var status = document.createElement("span");
    status.className = "visually-hidden";
    status.setAttribute("role", "status");
    button.addEventListener("click", function () {
      var labelNode = button.querySelector("span");
      writeClipboard(copyText(pre, lang)).then(function () {
        button.dataset.state = "copied";
        labelNode.textContent = "Copied";
        status.textContent = "Copied to clipboard";
      }, function () {
        button.dataset.state = "failed";
        labelNode.textContent = "Select and copy";
        status.textContent = "Copy failed; select the text instead";
      }).then(function () {
        window.setTimeout(function () {
          delete button.dataset.state;
          labelNode.textContent = idle;
          status.textContent = "";
        }, 1800);
      });
    });
    head.appendChild(button);
    head.appendChild(status);

    // Long lines scroll inside the block; keyboard users need to reach it.
    if (!pre.hasAttribute("tabindex")) pre.setAttribute("tabindex", "0");

    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(head);
    wrap.appendChild(pre);
  }

  registerGrammars(window.Prism);

  function run() {
    var blocks = document.querySelectorAll("pre");
    for (var i = 0; i < blocks.length; i++) frame(blocks[i]);
  }

  // Deferred: the DOM is complete, and Prism has not highlighted yet.
  run();
})();
