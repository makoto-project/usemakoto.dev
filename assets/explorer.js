/*
 * Makoto Explorer: step one dataset through the end-to-end proof.
 *
 * Every value shown is loaded from the published proof artifacts under
 * /demos/end-to-end/artifacts/: the data files, the signed statements (decoded
 * from their DSSE envelopes), the handoff manifest, and the verification
 * reports. The verified properties come from /explorer/properties.json, which
 * scripts/explorer_properties.py computes with core's own rules. Nothing here
 * re-implements verification; the page replays what the proof recorded.
 *
 * The stage and tamper choice live in the URL (?stage=3&tamper=rewired-step)
 * so a view can be shared.
 */
(function () {
  "use strict";

  var ART = "/demos/end-to-end/artifacts/";
  var ST = {
    origin: "56b7be4394fe09c62ec7a3d5763cecc251e9696f267f35b2acc717b0d170a27a",
    normalize: "1f28b72bcd4c1e9b7df71403ac6bb1670c2f2b09628ca6d76a2fa384db9a0848",
    publicSafe: "962be71738a0146642d27c87fba3c7338b0f2bb764b113b16867bb4808b11977"
  };

  var STAGES = [
    {
      title: "Capture the source",
      what: "A collector receives three customer records and signs an origin statement over their exact bytes. The statement names the source and the file's digest. Nothing came before it, so it is the root of the graph.",
      data: "customers.raw.json", prev: null,
      evidence: { kind: "statement", digest: ST.origin, label: "Origin statement" },
      adds: "One origin statement. Its subject digest is the hash of the data file shown with it.",
      level: "Origin L1 evidence: traceable capture"
    },
    {
      title: "Normalize",
      what: "A pipeline trims and lowercases emails, turns consent strings into booleans, and uppercases regions. It writes a new file and appends a transformation statement. The raw file is untouched.",
      data: "customers.normalized.json", prev: "customers.raw.json", match: "customer_id",
      evidence: { kind: "statement", digest: ST.normalize, label: "Transformation statement" },
      adds: "One transformation statement. Its input binds the raw file's digest and the origin statement as predecessor.",
      level: "Transform L1 evidence: traceable execution"
    },
    {
      title: "Make it public-safe",
      what: "A privacy step drops email addresses, replaces customer IDs with pseudonyms, and buckets ages. Another new file, another statement pointing back at the normalized one.",
      data: "customers.public.json", prev: "customers.normalized.json", match: "region",
      evidence: { kind: "statement", digest: ST.publicSafe, label: "Transformation statement" },
      adds: "One transformation statement. Its input binds the normalized file's digest and the normalize statement.",
      level: "Transform L1 evidence: traceable execution"
    },
    {
      title: "Hand it off",
      what: "The sender signs a handoff manifest over the exact set it is transferring: every statement, the root, the head, the final file, and the profile the receiver requires. The data bytes do not change.",
      data: "customers.public.json", prev: null,
      evidence: { kind: "manifest", label: "Handoff manifest" },
      adds: "One signed handoff manifest. It commits to exactly three statements, one root, one head, and one final artifact.",
      level: "The completeness anchor a receiver checks"
    },
    {
      title: "Receive and verify",
      what: "The receiver hashes the bytes that arrived, checks every signature against its own policy, walks the graph back to the root, and compares the handoff with the manifest and head digests it was told to expect.",
      data: "customers.public.json", prev: null,
      evidence: { kind: "report" },
      adds: "A verification report with sixteen checks, and the verified properties a summary would record.",
      level: "Receiver results: verified properties"
    }
  ];

  var ATTACKS = [
    { id: "", label: "Nothing: the real handoff", stage: 5 },
    { id: "edited-signed-metadata", label: "Edit a signed statement", stage: 3, codes: "E_SIGNATURE_INVALID", casebook: "/demos/04/",
      story: "Someone edits the public-safe statement's payload without the signing key. The old signature no longer matches the bytes." },
    { id: "rewired-step", label: "Rewire a step", stage: 3, codes: "E_SIGNATURE_INVALID", casebook: "/demos/02/",
      story: "Someone rewrites the public-safe step's predecessor binding to point somewhere else, without re-signing it." },
    { id: "unauthorized-signer", label: "Sign with an unauthorized key", stage: 3, codes: "E_SIGNER_UNAUTHORIZED", casebook: "/demos/03/",
      story: "The public-safe statement is signed by a key the receiver knows but has not authorized for that step. The signature itself is valid." },
    { id: "private-schema-violation", label: "Put email addresses back", stage: 3, codes: "E_PROFILE_INVALID", casebook: "/demos/05/",
      story: "The public-safe file is regenerated with email addresses and correctly re-signed. The receiver's pinned profile does not allow them." },
    { id: "removed-predecessor", label: "Drop the origin statement", stage: 4, codes: "E_PREDECESSOR_MISSING", casebook: "/demos/02/",
      story: "The handoff bundle is sent without the origin statement, so the chain no longer reaches its root." },
    { id: "statement-digest-mismatch", label: "Swap a statement under its index entry", stage: 4, codes: "E_STATEMENT_DIGEST", casebook: "/demos/04/",
      story: "An edited statement is placed in the bundle under the index entry of the original one." },
    { id: "mutated-final-data", label: "Change the final file in transit", stage: 5, codes: "E_ARTIFACT_DIGEST", casebook: "/demos/01/",
      story: "One byte is appended to the public-safe file after it was signed. Every signature still verifies." }
  ];

  var PROPERTIES = ["MAKOTO_AUTHORIZED", "MAKOTO_GRAPH_COMPLETE", "MAKOTO_FRESHNESS_ANCHORED", "MAKOTO_SCHEMA_CONFORMANT", "MAKOTO_REPRODUCED"];

  var root = document.querySelector("[data-explorer]");
  if (!root || !window.fetch) return;

  var cache = {};
  function load(path, kind) {
    var id = (kind || "json") + " " + path;
    if (!cache[id]) {
      cache[id] = fetch(path).then(function (r) {
        if (!r.ok) throw new Error(path + ": " + r.status);
        return kind === "bytes" ? r.arrayBuffer() : r.json();
      });
    }
    return cache[id];
  }
  function statement(digest) {
    return load(ART + "positive-bundle/attestations/" + digest + ".dsse.json").then(decode);
  }
  function decode(envelope) {
    var bin = atob(envelope.payload), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  function sha256(buffer) {
    if (!window.crypto || !crypto.subtle) return Promise.resolve(null);
    return crypto.subtle.digest("SHA-256", buffer).then(function (h) {
      return Array.prototype.map.call(new Uint8Array(h), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    });
  }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function scalar(v) {
    if (typeof v === "string") return '<span class="token string">' + esc(JSON.stringify(v)) + "</span>";
    if (typeof v === "number") return '<span class="token number">' + v + "</span>";
    if (typeof v === "boolean") return '<span class="token boolean">' + v + "</span>";
    if (v === null) return '<span class="token null">null</span>';
    return "";
  }
  function key(k) {
    return '<span class="token property">' + esc(JSON.stringify(k)) + '</span><span class="token punctuation">:</span> ';
  }
  function punct(s) { return '<span class="token punctuation">' + s + "</span>"; }

  /* Lay a value out one member per line. mark(path, value) returns a class for a line. */
  function lines(value, mark) {
    var out = [];
    function walk(v, depth, prefix, path, comma) {
      var pad = "", c = comma ? punct(",") : "";
      for (var i = 0; i < depth; i++) pad += "  ";
      if (v && typeof v === "object") {
        var arr = Array.isArray(v), keys = arr ? v.map(function (_, i) { return i; }) : Object.keys(v);
        var open = arr ? "[" : "{", close = arr ? "]" : "}";
        if (!keys.length) { out.push({ html: pad + prefix + punct(open + close) + c, cls: mark(path, v), depth: depth }); return; }
        out.push({ html: pad + prefix + punct(open), cls: mark(path, v, "open"), depth: depth });
        keys.forEach(function (k, idx) {
          walk(v[k], depth + 1, arr ? "" : key(k), path.concat([k]), idx < keys.length - 1);
        });
        var extra = mark(path.concat(["__removed__"]), v) || [];
        extra.forEach(function (line) { out.push({ html: pad + "  " + line, cls: "is-removed", depth: depth + 1 }); });
        out.push({ html: pad + punct(close) + c, cls: "", depth: depth });
        return;
      }
      out.push({ html: pad + prefix + scalar(v) + c, cls: mark(path, v), depth: depth });
    }
    walk(value, 0, "", [], false);
    return out;
  }

  function renderLines(pre, rows, changesOnly) {
    var html = rows.map(function (row) {
      var hidden = changesOnly && !row.cls && row.depth > 1 ? " hidden" : "";
      return '<span class="line' + (row.cls ? " " + row.cls : "") + '"' + hidden + ' style="--indent:' + Math.min(row.depth * 2, 12) + '">' + row.html + "</span>";
    }).join("");
    pre.querySelector("code").innerHTML = html;
  }

  /* Data diff: match each row with its predecessor row by a field, then mark added, changed, removed members. */
  function dataRows(current, previous, match) {
    var byKey = {};
    if (previous) {
      previous.forEach(function (row) {
        var k = String(row[match]).trim().toUpperCase();
        byKey[k] = row;
      });
    }
    return lines(current, function (path, v, open) {
      var removedMarker = path[path.length - 1] === "__removed__";
      if (removedMarker && (path.length !== 2 || !previous)) return [];
      if (!previous || path.length < 1) return "";
      var row = current[path[0]], before = byKey[String(row[match]).trim().toUpperCase()];
      if (!before) return path.length === 1 && open ? "is-added" : "";
      if (path.length === 2 && path[1] === "__removed__") {
        return Object.keys(before).filter(function (k) { return !(k in row); }).map(function (k) {
          return key(k) + scalar(before[k]);
        });
      }
      if (path.length !== 2) return "";
      var field = path[1];
      if (!(field in before)) return "is-added";
      return JSON.stringify(before[field]) === JSON.stringify(v) ? "" : "is-changed";
    });
  }

  function linkRows(value, links) {
    return lines(value, function (path, v) {
      if (path[path.length - 1] === "__removed__") return [];
      return typeof v === "string" && links.indexOf(v) !== -1 ? "is-link" : "";
    });
  }

  function short(d) { return d ? "sha256:" + d.slice(0, 7) : ""; }

  /* ---------- DOM ---------- */
  var q = function (sel) { return root.querySelector(sel); };
  var stageNav = q("[data-stage-nav]");
  var titleEl = q("[data-stage-title]"), countEl = q("[data-stage-count]"), whatEl = q("[data-stage-what]"), levelEl = q("[data-stage-level]");
  var dataName = q("[data-data-name]"), dataPre = q("[data-data] pre"), dataNote = q("[data-data-note]");
  var evName = q("[data-evidence-name]"), evPre = q("[data-evidence] pre"), evNote = q("[data-evidence-note]");
  var receiver = q("[data-receiver]"), tamperSelect = q("[data-tamper]"), tamperStory = q("[data-tamper-story]");
  var chainEl = q("[data-chain]"), changesToggle = q("[data-changes-only]");
  var prevBtn = q("[data-prev]"), nextBtn = q("[data-next]");

  var state = { stage: 1, tamper: "", changesOnly: false };
  try {
    var params = new URLSearchParams(window.location.search);
    var s = parseInt(params.get("stage"), 10);
    if (s >= 1 && s <= STAGES.length) state.stage = s;
    var t = params.get("tamper") || "";
    if (ATTACKS.some(function (a) { return a.id === t; })) state.tamper = t;
  } catch (e) { /* keep defaults */ }

  STAGES.forEach(function (stage, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "explorer-stage";
    b.innerHTML = '<span class="explorer-stage-n">' + (i + 1) + "</span> " + esc(stage.title);
    b.addEventListener("click", function () { go(i + 1); });
    stageNav.appendChild(b);
  });
  ATTACKS.forEach(function (a) {
    var o = document.createElement("option");
    o.value = a.id;
    o.textContent = a.id ? a.label + " (stage " + a.stage + ")" : a.label;
    tamperSelect.appendChild(o);
  });

  tamperStory.addEventListener("click", function (event) {
    if (!event.target.closest("[data-to-receiver]")) return;
    event.preventDefault();
    go(5);
  });
  prevBtn.addEventListener("click", function () { go(state.stage - 1); });
  nextBtn.addEventListener("click", function () { go(state.stage + 1); });
  tamperSelect.addEventListener("change", function () { state.tamper = tamperSelect.value; sync(); render(); });
  changesToggle.addEventListener("click", function () {
    state.changesOnly = !state.changesOnly;
    changesToggle.setAttribute("aria-pressed", state.changesOnly ? "true" : "false");
    Array.prototype.forEach.call(dataPre.querySelectorAll(".line"), function (line) {
      line.hidden = state.changesOnly && !/is-(added|changed|removed)/.test(line.className) && parseInt(line.style.getPropertyValue("--indent"), 10) > 2;
    });
  });

  function go(n) {
    if (n < 1 || n > STAGES.length) return;
    state.stage = n;
    sync();
    render();
  }
  function sync() {
    try {
      var params = new URLSearchParams();
      if (state.stage !== 1) params.set("stage", state.stage);
      if (state.tamper) params.set("tamper", state.tamper);
      var qs = params.toString();
      history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
    } catch (e) { /* sharing is a convenience */ }
  }

  var token = 0;
  function render() {
    var mine = ++token, stage = STAGES[state.stage - 1];
    var attack = ATTACKS.filter(function (a) { return a.id === state.tamper; })[0] || ATTACKS[0];
    Array.prototype.forEach.call(stageNav.children, function (b, i) {
      if (i === state.stage - 1) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      b.classList.toggle("is-tampered", !!attack.id && attack.stage === i + 1);
    });
    countEl.textContent = "Stage " + state.stage + " of " + STAGES.length;
    titleEl.textContent = stage.title;
    whatEl.textContent = stage.what;
    levelEl.textContent = stage.level;
    prevBtn.disabled = state.stage === 1;
    nextBtn.disabled = state.stage === STAGES.length;
    tamperStory.innerHTML = attack.id
      ? "<strong>At stage " + attack.stage + ":</strong> " + esc(attack.story) + ' The receiver denies it with <code>' + attack.codes + '</code>. ' + (state.stage === 5 ? "" : '<a href="?stage=5&amp;tamper=' + attack.id + '" data-to-receiver>See what the receiver decides</a> · ') + '<a href="' + attack.casebook + '">See this attack as a case</a>.'
      : "The untampered handoff. Pick an attack to see the same receiver deny it.";

    var dataPath = ART + "data/" + stage.data;
    var jobs = [load(dataPath, "bytes").then(function (buf) { return sha256(buf).then(function (h) { return { json: JSON.parse(new TextDecoder().decode(buf)), digest: h }; }); })];
    jobs.push(stage.prev && stage.prev !== stage.data ? load(ART + "data/" + stage.prev) : Promise.resolve(null));
    jobs.push(evidence(stage, attack));
    jobs.push(chain(state.stage, attack));

    Promise.all(jobs).then(function (r) {
      if (mine !== token) return;
      var data = r[0], previous = r[1], ev = r[2];
      dataName.textContent = stage.data + (data.digest ? " · " + short(data.digest) : "");
      if (data.digest) dataName.title = "sha256:" + data.digest + " (hashed in your browser)";
      renderLines(dataPre, dataRows(data.json, previous, stage.match), false);
      changesToggle.hidden = !previous;
      changesToggle.setAttribute("aria-pressed", "false");
      state.changesOnly = false;
      dataNote.textContent = state.stage === 5 && attack.id === "mutated-final-data"
        ? "The receiver was handed these bytes plus one appended byte, so their hash no longer matches the signed digest."
        : !previous
          ? (state.stage === 4 ? "Unchanged: the handoff signs over the same bytes." : state.stage === 5 ? "What arrived. The receiver hashes it before trusting anything." : "The first bytes Makoto sees.")
          : "Highlighted: members added, changed, or removed since the previous stage.";
      evName.textContent = ev.name;
      renderLines(evPre, ev.rows, false);
      evNote.innerHTML = ev.note;
      receiver.innerHTML = ev.receiver || "";
      chainEl.innerHTML = r[3];
    }).catch(function (error) {
      if (mine !== token) return;
      whatEl.textContent = "This view could not load its artifacts (" + error.message + "). The files are published under /demos/end-to-end/artifacts/.";
    });
  }

  function evidence(stage, attack) {
    var e = stage.evidence;
    if (e.kind === "statement") {
      var prevDigest = stage.prev ? (state.stage === 2 ? ST.origin : ST.normalize) : null;
      return Promise.all([statement(e.digest), stage.prev ? load(ART + "data/" + stage.prev, "bytes").then(sha256) : Promise.resolve(null)]).then(function (r) {
        var links = [prevDigest, r[1]].filter(Boolean);
        return {
          name: e.label + " · " + short(e.digest),
          rows: linkRows(r[0], links),
          note: links.length
            ? "Highlighted: the digests that bind this step to the one before it. " + esc(stage.adds)
            : esc(stage.adds)
        };
      });
    }
    if (e.kind === "manifest") {
      return load(ART + "positive-bundle/manifest.dsse.json").then(function (env) {
        return {
          name: e.label + " · signed by the sender",
          rows: linkRows(decode(env), [ST.origin, ST.normalize, ST.publicSafe]),
          note: "Highlighted: the three statements from the previous stages. " + esc(stage.adds)
        };
      });
    }
    var reportName = attack.id || "positive";
    return Promise.all([load(ART + "reports/" + reportName + ".json"), load("/explorer/properties.json")]).then(function (r) {
      var report = r[0], props = r[1][reportName];
      var checks = report.checks.map(function (c) { return { id: c.id, status: c.status }; });
      var rows = lines({ decision: report.decision, checks: checks, errors: report.errors.map(function (x) { return { code: x.code, message: x.message }; }) }, function (path, v) {
        if (path[path.length - 1] === "__removed__") return [];
        if (path[0] === "decision") return v === "allow" ? "is-pass" : "is-fail";
        if (path[0] === "checks" && path.length === 3 && path[2] === "status") return v === "pass" ? "" : "is-fail";
        if (path[0] === "errors" && path.length === 3 && path[2] === "code") return "is-fail";
        return "";
      });
      var established = PROPERTIES.map(function (p) {
        var ok = props && props[p];
        return "<tr><td><a href=\"/levels/#property-" + p.slice(7).toLowerCase().replace(/_/g, "-") + "\"><code>" + p + "</code></a></td><td>" + (ok ? "Established" : "Not established") + "</td></tr>";
      }).join("");
      return {
        name: "Verification report · " + reportName + ".json",
        rows: rows,
        note: 'Highlighted: the decision, and every check and error that stopped it. <a href="' + ART + "reports/" + reportName + '.json">Open the full report</a>.',
        receiver: '<h3 class="explorer-receiver-title">Decision: <span class="' + (report.decision === "allow" ? "is-allow" : "is-deny") + '">' + report.decision + "</span></h3>" +
          "<p>" + (report.decision === "allow"
            ? "Every check passed. A verification summary over this report records these properties:"
            : "A verification summary over this report is <code>FAILED</code>. Its evaluation sidecar still records which properties the report supports:") + "</p>" +
          '<table><thead><tr><th>Verified property</th><th>Result</th></tr></thead><tbody>' + established + "</tbody></table>" +
          '<p class="explorer-small"><code>MAKOTO_REPRODUCED</code> needs a second run on an independent platform, which this proof does not include.</p>'
      };
    });
  }

  function chain(n, attack) {
    var items = [
      { at: 1, label: "Origin", digest: ST.origin },
      { at: 2, label: "Normalize", digest: ST.normalize },
      { at: 3, label: "Public-safe", digest: ST.publicSafe }
    ].filter(function (i) { return i.at <= n; });
    var html = items.map(function (i, idx) {
      return "<li><span>" + esc(i.label) + '</span> <code class="hash" title="sha256:' + i.digest + '">' + i.digest.slice(0, 7) + "</code>" + (idx === 0 ? " root" : "") + (idx === items.length - 1 && n >= 3 ? " head" : "") + "</li>";
    });
    if (n >= 4) html.push("<li><span>Handoff manifest</span> signed</li>");
    if (n >= 5) html.push("<li><span>Receiver</span> " + (attack.id ? "denied" : "allowed") + "</li>");
    return Promise.resolve(html.join(""));
  }

  tamperSelect.value = state.tamper;
  render();
})();
