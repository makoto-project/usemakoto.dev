/*
 * Exhibit frames for every code block: a tab with the filename and language,
 * a copy control, a terminal treatment for shell sessions, wrapped lines that
 * hang past their own indentation, and a reading layout for JSON.
 *
 * Load order matters. This script is deferred directly after /assets/prism.js,
 * so it runs after Prism registers its languages but before Prism's own
 * DOMContentLoaded highlightAll. That window is where the terminal grammars
 * are registered, shell blocks are re-classed, and JSON is laid out, so Prism
 * highlights each block once with the right grammar. Without Prism (pages
 * with plain <pre> only) the frames, line wrapping and copy still work.
 *
 * The published bytes are never lost: copy always takes the original text,
 * and a reformatted JSON block keeps its original bytes one click away.
 */
(function () {
  "use strict";

  var LABELS = {
    yaml: "yaml", json: "json", python: "python", javascript: "javascript",
    typescript: "typescript", go: "go", sql: "sql", bash: "shell",
    terminal: "terminal", "shell-plain": "shell", none: "text", markup: "html"
  };
  var PRISM_SELECTOR = 'code[class*="language-"], [class*="language-"] code, code[class*="lang-"], [class*="lang-"] code';

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
    // Every highlight pass (the first, and each exact-bytes toggle) ends by
    // splitting the result into lines.
    Prism.hooks.add("complete", function (env) {
      if (!env.element) return;
      if (env.language === "terminal" || env.language === "shell-plain") {
        abbreviateDigests(env.element);
      }
      splitLines(env.element);
      if (env.language === "terminal" || env.language === "shell-plain") {
        markDiagnostics(env.element);
      }
    });
  }

  /*
   * Shell sessions show digests the way GitHub shows a commit: algorithm plus
   * the first seven hex digits. Display only. The full value stays in the
   * title, and Copy always takes the original text.
   */
  function abbreviateDigests(code) {
    var tokens = code.querySelectorAll(".token.digest");
    for (var i = 0; i < tokens.length; i++) {
      var full = tokens[i].textContent;
      var match = /^(sha256:)([0-9a-f]{7})[0-9a-f]+$/.exec(full);
      if (!match) continue;
      tokens[i].title = full;
      tokens[i].textContent = match[1] + match[2];
    }
  }

  /*
   * A diagnostic message (a line that begins with an E_ or W_ code) stays on
   * one line and is cut with an ellipsis when the frame is too narrow. The
   * full message is in the title and in Copy.
   */
  function markDiagnostics(code) {
    var lines = code.querySelectorAll(":scope > .line");
    for (var i = 0; i < lines.length; i++) {
      var text = lines[i].textContent;
      if (!/^[EW]_[A-Z0-9_]{3,}\b/.test(text)) continue;
      lines[i].classList.add("is-diagnostic");
      lines[i].title = text.replace(/\n$/, "");
    }
  }

  function languageOf(code) {
    var match = /(?:^|\s)language-([\w-]+)/.exec(code.className || "");
    return match ? match[1] : "none";
  }

  function isTranscript(text) {
    return /^\$ /m.test(text);
  }

  /*
   * Lay a JSON document out one member per line with two-space indentation.
   * This is a lexical re-indent, not JSON.parse + stringify: every string and
   * number literal is copied through verbatim and key order is kept, so the
   * displayed document parses to exactly what the original parses to. The
   * same algorithm is mirrored in tests/test_layout_guards.py. Returns null
   * when the text is not a single valid JSON document.
   */
  function layoutJson(text) {
    try { JSON.parse(text); } catch (e) { return null; }
    var out = "", depth = 0, i = 0, n = text.length, pad = "  ";
    function newline() { out += "\n"; for (var d = 0; d < depth; d++) out += pad; }
    while (i < n) {
      var ch = text.charAt(i);
      if (ch === '"') {
        var j = i + 1;
        while (j < n) {
          var c = text.charAt(j);
          if (c === "\\") { j += 2; continue; }
          if (c === '"') break;
          j++;
        }
        out += text.slice(i, j + 1);
        i = j + 1;
      } else if (ch === "{" || ch === "[") {
        var k = i + 1;
        while (k < n && /\s/.test(text.charAt(k))) k++;
        var close = ch === "{" ? "}" : "]";
        if (text.charAt(k) === close) { out += ch + close; i = k + 1; continue; }
        out += ch; depth++; newline(); i++;
      } else if (ch === "}" || ch === "]") {
        depth--; newline(); out += ch; i++;
      } else if (ch === ",") {
        out += ","; newline(); i++;
      } else if (ch === ":") {
        out += ": "; i++;
      } else if (/\s/.test(ch)) {
        i++;
      } else {
        out += ch; i++;
      }
    }
    return out;
  }

  /*
   * Wrap each source line of a rendered block in <span class="line"> so CSS
   * can hang wrapped continuations past the line's own indentation. Works on
   * the highlighted markup: token spans that cross a newline are closed at
   * the end of the line and reopened on the next. textContent is unchanged.
   */
  function splitLines(code) {
    if (code.querySelector(":scope > .line")) return;
    var html = code.innerHTML;
    var parts = html.split(/(<[^>]+>)/);
    var stack = [], out = '<span class="line">';
    for (var p = 0; p < parts.length; p++) {
      var part = parts[p];
      if (!part) continue;
      if (part.charAt(0) === "<") {
        if (part.charAt(1) === "/") { stack.pop(); }
        else if (!/\/>$/.test(part)) { stack.push(part); }
        out += part;
        continue;
      }
      var pieces = part.split("\n");
      for (var q = 0; q < pieces.length; q++) {
        if (q > 0) {
          var closes = "", opens = "";
          for (var s = stack.length - 1; s >= 0; s--) {
            closes += "</" + /^<([\w-]+)/.exec(stack[s])[1] + ">";
          }
          for (var o = 0; o < stack.length; o++) opens += stack[o];
          out += "\n" + closes + '</span><span class="line">' + opens;
        }
        out += pieces[q];
      }
    }
    out += "</span>";
    code.innerHTML = out;
    var lines = code.querySelectorAll(":scope > .line");
    for (var l = 0; l < lines.length; l++) {
      var lead = /^[ \t]*/.exec(lines[l].textContent)[0].replace(/\t/g, "  ").length;
      if (lead) lines[l].style.setProperty("--indent", Math.min(lead, 12));
    }
  }

  function copyText(original, lang) {
    var text = original.replace(/\n$/, "");
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

  function willHighlight(code) {
    return !!(window.Prism && !window.Prism.manual && code.matches && code.matches(PRISM_SELECTOR));
  }

  function render(code) {
    if (willHighlight(code) && window.Prism.highlightElement && document.readyState !== "loading") {
      window.Prism.highlightElement(code);
    } else if (!willHighlight(code)) {
      splitLines(code);
    }
  }

  function frame(pre) {
    if (pre.closest(".exhibit") || pre.dataset.exhibit === "off") return;
    var code = pre.querySelector("code") || pre;
    var lang = languageOf(code);
    if (lang === "none") lang = languageOf(pre);
    var original = code.textContent;

    if (lang === "bash") {
      lang = isTranscript(original) ? "terminal" : "shell-plain";
      code.className = code.className.replace(/(^|\s)language-bash(?=\s|$)/, "$1language-" + lang);
      pre.className = pre.className.replace(/(^|\s)language-bash(?=\s|$)/, "$1language-" + lang);
    }
    var terminal = lang === "terminal" || lang === "shell-plain";

    var wrap = document.createElement("div");
    wrap.className = "exhibit" + (terminal ? " is-terminal" : "");
    wrap.dataset.lang = lang;

    var head = document.createElement("div");
    head.className = "exhibit-head";

    var filename = pre.dataset.filename || code.dataset.filename;
    if (filename) {
      var name = document.createElement("span");
      name.className = "exhibit-name";
      name.textContent = filename;
      // data-digest="sha256:<hex>" shows as a short SHA; hover and copy give the full hex.
      var digest = /^sha256:([0-9a-f]{64})$/.exec(pre.dataset.digest || "");
      if (digest) {
        var hash = document.createElement("code");
        hash.className = "hash exhibit-digest";
        hash.textContent = "sha256:" + digest[1].slice(0, 7);
        hash.title = "sha256:" + digest[1];
        hash.dataset.full = digest[1];
        name.appendChild(document.createTextNode(" · "));
        name.appendChild(hash);
      }
      head.appendChild(name);
    }

    var label = document.createElement("span");
    label.className = "exhibit-lang";
    label.textContent = LABELS[lang] || lang;
    head.appendChild(label);

    var spacer = document.createElement("span");
    spacer.className = "exhibit-spacer";
    head.appendChild(spacer);

    // JSON is shown one member per line. The original bytes stay available.
    var laidOut = lang === "json" && code !== pre ? layoutJson(original) : null;
    var trailing = /\n$/.test(original) ? "\n" : "";
    var note = null;
    if (laidOut !== null && laidOut + trailing !== original) {
      code.textContent = laidOut + trailing;
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "exhibit-toggle";
      toggle.textContent = "Exact bytes";
      toggle.setAttribute("aria-pressed", "false");
      toggle.addEventListener("click", function () {
        var exact = toggle.getAttribute("aria-pressed") !== "true";
        toggle.setAttribute("aria-pressed", exact ? "true" : "false");
        code.textContent = exact ? original : laidOut + trailing;
        note.textContent = exact
          ? "The exact published bytes, wrapped to fit the frame."
          : "Formatted for reading. A digest covers the exact published bytes; Copy and Exact bytes give you those.";
        render(code);
      });
      head.appendChild(toggle);
      note = document.createElement("p");
      note.className = "exhibit-note";
      note.textContent = "Formatted for reading. A digest covers the exact published bytes; Copy and Exact bytes give you those.";
    }

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
      writeClipboard(copyText(original, lang)).then(function () {
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

    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(head);
    if (note) wrap.appendChild(note);
    wrap.appendChild(pre);

    // Blocks Prism will not touch are split now; the rest after highlighting.
    if (!willHighlight(code)) splitLines(code);
  }

  registerGrammars(window.Prism);

  function run() {
    var blocks = document.querySelectorAll("pre");
    for (var i = 0; i < blocks.length; i++) frame(blocks[i]);
  }

  // Copying a short SHA (all or part of it) copies the full digest instead.
  document.addEventListener("copy", function (event) {
    var selection = window.getSelection && window.getSelection();
    if (!selection || selection.isCollapsed || !event.clipboardData) return;
    function element(node) { return node && (node.nodeType === 1 ? node : node.parentElement); }
    var start = element(selection.anchorNode), end = element(selection.focusNode);
    var hash = start && start.closest("[data-full]");
    if (!hash || !end || end.closest("[data-full]") !== hash) return;
    event.clipboardData.setData("text/plain", hash.dataset.full);
    event.preventDefault();
  });

  // Deferred: the DOM is complete, and Prism has not highlighted yet.
  run();
})();
