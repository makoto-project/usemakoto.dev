/*
 * Flow graphs: connector lines, and small points of light travelling along
 * them, drawn into a decorative SVG layer underneath the nodes of a figure.
 *
 * A host element carries data-flow="<kind>" and class "flow":
 *   chain      consecutive children (.dag-node) in order
 *   spread     one .spread-source fanning out to every .spread-node; a node
 *              carrying data-copies="3" receives three separate lines
 *   lifecycle  explicit edges between [data-flow-id] nodes
 *   inplace    commands feeding one table (db), the table's exports flowing
 *              to statements (st-N), and each statement pointing back to the
 *              one before it; sparks keep time with the CSS cycle in v02.css
 *
 * Geometry is measured from the rendered boxes and recomputed whenever the
 * host resizes, so lines land on the boxes at every width and every stacking.
 * Under prefers-reduced-motion the lines are drawn and nothing moves. The
 * layer is aria-hidden; each figure's text says what the lines show.
 */
(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var motion = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var SPEED = 45;       // px per second for a travelling point
  var uid = 0;

  function still() { return !!(motion && motion.matches); }

  function el(name, attrs, parent) {
    var node = document.createElementNS(NS, name);
    for (var key in attrs) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function box(node, origin) {
    var r = node.getBoundingClientRect();
    var b = { l: r.left - origin.left, t: r.top - origin.top, r: r.right - origin.left, b: r.bottom - origin.top };
    b.cx = (b.l + b.r) / 2; b.cy = (b.t + b.b) / 2; b.w = b.r - b.l; b.h = b.b - b.t;
    return b;
  }

  // Orthogonal polyline with softened corners.
  function pathData(points) {
    var d = "M" + points[0][0].toFixed(1) + " " + points[0][1].toFixed(1);
    for (var i = 1; i < points.length; i++) {
      var p = points[i], prev = points[i - 1], next = points[i + 1];
      if (!next) { d += " L" + p[0].toFixed(1) + " " + p[1].toFixed(1); break; }
      var inLen = Math.hypot(p[0] - prev[0], p[1] - prev[1]);
      var outLen = Math.hypot(next[0] - p[0], next[1] - p[1]);
      var r = Math.min(8, inLen / 2, outLen / 2);
      if (r < 1) { d += " L" + p[0].toFixed(1) + " " + p[1].toFixed(1); continue; }
      var ax = p[0] - (p[0] - prev[0]) / inLen * r, ay = p[1] - (p[1] - prev[1]) / inLen * r;
      var bx = p[0] + (next[0] - p[0]) / outLen * r, by = p[1] + (next[1] - p[1]) / outLen * r;
      d += " L" + ax.toFixed(1) + " " + ay.toFixed(1) + " Q" + p[0].toFixed(1) + " " + p[1].toFixed(1) + " " + bx.toFixed(1) + " " + by.toFixed(1);
    }
    return d;
  }

  function length(points) {
    var total = 0;
    for (var i = 1; i < points.length; i++) total += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    return total;
  }

  function Layer(host) {
    var old = host.querySelector(":scope > .flow-layer");
    if (old) old.remove();
    var origin = host.getBoundingClientRect();
    this.origin = origin;
    this.id = "flow" + (++uid);
    this.svg = el("svg", { "class": "flow-layer", "aria-hidden": "true", focusable: "false",
      width: origin.width, height: origin.height, viewBox: "0 0 " + origin.width + " " + origin.height });
    var defs = el("defs", {}, this.svg);
    var marker = el("marker", { id: this.id + "-head", viewBox: "0 0 10 10", refX: "9", refY: "5",
      markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse", markerUnits: "userSpaceOnUse" }, defs);
    el("path", { d: "M0 0 L10 5 L0 10 z", "class": "flow-head" }, marker);
    this.count = 0;
    host.insertBefore(this.svg, host.firstChild);
  }

  Layer.prototype.box = function (node) { return box(node, this.origin); };

  // Seconds a point takes to cross one edge.
  function travelTime(points, opts) {
    var seconds = Math.max(1.2, length(points) / ((opts && opts.speed) || SPEED));
    return opts && opts.maxTravel ? Math.min(seconds, opts.maxTravel) : seconds;
  }

  // opts: back (dashed, seal-coloured point), arrow, spark, delay, cycle, speed, hidden
  Layer.prototype.edge = function (points, opts) {
    opts = opts || {};
    var id = this.id + "-p" + (++this.count);
    var path = el("path", { id: id, d: pathData(points), "class": "flow-path" + (opts.back ? " is-back" : "") }, this.svg);
    if (opts.hidden) path.setAttribute("stroke", "none");
    if (opts.arrow !== false && !opts.hidden) path.setAttribute("marker-end", "url(#" + this.id + "-head)");
    if (opts.spark === false || still()) return path;
    var travel = travelTime(points, opts);
    var cycle = Math.max(opts.cycle || 0, travel + 1.4);
    var f = (travel / cycle).toFixed(3);
    var dot = el("circle", { r: opts.back ? "3" : "2.6", "class": "flow-spark" + (opts.back ? " is-back" : ""), opacity: "0" }, this.svg);
    var begin = (opts.delay || 0).toFixed(2) + "s";
    var move = el("animateMotion", { dur: cycle.toFixed(2) + "s", begin: begin, repeatCount: "indefinite",
      calcMode: "linear", keyPoints: "0;1;1", keyTimes: "0;" + f + ";1" }, dot);
    el("mpath", { href: "#" + id }, move);
    el("animate", { attributeName: "opacity", dur: cycle.toFixed(2) + "s", begin: begin, repeatCount: "indefinite",
      values: "0;1;1;0;0", keyTimes: "0;" + (f * 0.12).toFixed(3) + ";" + (f * 0.85).toFixed(3) + ";" + f + ";1" }, dot);
    return path;
  };

  function intersects(b, x1, y1, x2, y2) {
    var l = Math.min(x1, x2), r = Math.max(x1, x2), t = Math.min(y1, y2), bt = Math.max(y1, y2);
    return l < b.r - 1 && r > b.l + 1 && t < b.b - 1 && bt > b.t + 1;
  }

  /*
   * Route from box a to box b. Side by side: facing edges. Stacked: bottom to
   * top, unless another node sits in the way, in which case the line leaves
   * a's side, runs down a gutter beside the column, and enters b's side.
   */
  function route(a, b, others, side, offset) {
    offset = offset || 0;
    var sameRow = a.t < b.b - 2 && b.t < a.b - 2;
    if (sameRow && (b.l >= a.r - 2 || a.l >= b.r - 2)) {
      var ltr = b.l >= a.r - 2;
      var x1 = ltr ? a.r : a.l, x2 = ltr ? b.l : b.r, y1 = a.cy, y2 = b.cy;
      if (Math.abs(y1 - y2) < 2) return [[x1, y1], [x2, y2]];
      var mx = (x1 + x2) / 2;
      return [[x1, y1], [mx, y1], [mx, y2], [x2, y2]];
    }
    var down = b.t >= a.b - 2;
    var ox = (Math.max(a.l, b.l) + Math.min(a.r, b.r)) / 2;
    var sy = down ? a.b : a.t, ey = down ? b.t : b.b;
    var blocked = others.some(function (o) { return intersects(o, ox, sy, ox, ey); });
    if (!blocked) {
      if (Math.abs(a.cx - b.cx) < 2 || (ox > a.l && ox < a.r && ox > b.l && ox < b.r)) return [[ox, sy], [ox, ey]];
      var my = (sy + ey) / 2;
      return [[a.cx, sy], [a.cx, my], [b.cx, my], [b.cx, ey]];
    }
    if (!sameRow && !(b.t >= a.b - 2 || a.t >= b.b - 2)) blocked = true;
    var gx = side === "right" ? Math.max(a.r, b.r) + 14 + offset : Math.min(a.l, b.l) - 14 - offset;
    var ax = side === "right" ? a.r : a.l, bx = side === "right" ? b.r : b.l;
    return [[ax, a.cy], [gx, a.cy], [gx, b.cy], [bx, b.cy]];
  }

  function drawChain(host) {
    var nodes = Array.prototype.slice.call(host.querySelectorAll(":scope > .dag-node"));
    var layer = new Layer(host);
    var boxes = nodes.map(function (n) { return layer.box(n); });
    // One point walks the chain: each edge's point leaves only when the point
    // before it has landed, and every edge shares one cycle so the relay
    // stays in step on every repeat.
    var routes = [], starts = [], total = 0;
    for (var i = 0; i < boxes.length - 1; i++) {
      var others = boxes.filter(function (_, k) { return k !== i && k !== i + 1; });
      routes.push(route(boxes[i], boxes[i + 1], others, "left"));
      starts.push(total);
      // A wrapped row's return line is long; cap it so the relay keeps pace.
      total += travelTime(routes[i], { maxTravel: 2.4 });
    }
    var cycle = Math.max(3.6, total + 1.4);
    for (var j = 0; j < routes.length; j++) {
      layer.edge(routes[j], { delay: starts[j], cycle: cycle, maxTravel: 2.4 });
    }
  }

  function drawSpread(host) {
    var source = host.querySelector(".spread-source");
    var nodes = Array.prototype.slice.call(host.querySelectorAll(".spread-node"));
    var label = host.querySelector(".spread-arrow");
    if (!source || !nodes.length) return;
    var layer = new Layer(host);
    var S = layer.box(source);
    var boxes = nodes.map(function (n) { return layer.box(n); });
    var gridTop = Math.min.apply(null, boxes.map(function (b) { return b.t; }));
    var firstRow = boxes.filter(function (b) { return b.t < gridTop + 4; });

    // One line per copy. Top-row nodes are entered from above; every deeper
    // node is reached down the gutter on its left.
    var lines = [];
    boxes.forEach(function (b, i) {
      var copies = parseInt(nodes[i].getAttribute("data-copies") || "1", 10);
      for (var c = 0; c < copies; c++) {
        var spread = (c - (copies - 1) / 2);
        lines.push({ b: b, top: firstRow.indexOf(b) !== -1, spread: spread, order: i + c / 10 });
      }
    });
    // Stacked in one column, the copies share one trunk down the gutter and
    // each branches off at its own node: one line to read, many points of
    // light peeling away along it. Side by side, every copy keeps its own
    // lane so no drop crosses another node.
    var bandTop = (label ? layer.box(label).b : S.b) + 12;
    var bandBottom = gridTop - 14;
    var single = boxes.every(function (b) { return Math.abs(b.l - boxes[0].l) < 2; });
    if (single) {
      var trunk = boxes[0].l - 14;
      lines.forEach(function (line, i) {
        var ey = line.b.cy + line.spread * 12;
        layer.edge([[S.cx, S.b], [S.cx, bandTop], [trunk, bandTop], [trunk, ey], [line.b.l, ey]],
          { delay: (i * 0.53) % 4.2, cycle: 5.2 });
      });
      return;
    }

    // Gutter lanes: the shallowest line in a gutter runs closest to its nodes.
    var gutters = {};
    lines.forEach(function (line) {
      if (line.top) { line.dx = line.b.cx + line.spread * 16; return; }
      var key = Math.round(line.b.l);
      (gutters[key] = gutters[key] || []).push(line);
    });
    Object.keys(gutters).forEach(function (key) {
      gutters[key].sort(function (p, q) { return p.b.cy - q.b.cy || p.spread - q.spread; });
      gutters[key].forEach(function (line, rank) { line.dx = line.b.l - 9 - rank * 5; });
    });
    lines.sort(function (p, q) { return p.dx - q.dx || p.order - q.order; });

    // Ports along the source's lower edge, in the same left-to-right order.
    var n = lines.length, inset = Math.min(28, S.w / 6);
    lines.forEach(function (line, i) {
      line.px = n === 1 ? S.cx : S.l + inset + (S.w - 2 * inset) * i / (n - 1);
    });
    // Bus levels: outermost lines turn first, so no drop crosses a run.
    var left = lines.filter(function (l) { return l.dx <= l.px; });
    var right = lines.filter(function (l) { return l.dx > l.px; }).reverse();
    [left, right].forEach(function (group) {
      var step = group.length > 1 ? Math.min(7, (bandBottom - bandTop) / (group.length - 1)) : 0;
      group.forEach(function (line, i) { line.y = bandTop + step * i; });
    });

    lines.forEach(function (line, i) {
      var b = line.b, pts;
      if (line.top) {
        pts = [[line.px, S.b], [line.px, line.y], [line.dx, line.y], [line.dx, b.t]];
      } else {
        var ey = b.cy + line.spread * 12;
        pts = [[line.px, S.b], [line.px, line.y], [line.dx, line.y], [line.dx, ey], [b.l, ey]];
      }
      layer.edge(pts, { delay: (i * 0.53) % 4.2, cycle: 5.2 });
    });
  }

  // Explicit edge lists for authored figures. [from, to, options]
  var EDGES = {
    // The homepage hero: the gate a receiver adds, then the run it produced.
    handoff: [
      ["gate", "run", { side: "left", delay: 0.9, cycle: 4.2 }]
    ],
    lifecycle: [
      ["raw", "normalized", { side: "left", delay: 0, cycle: 4.5 }],
      ["normalized", "public", { side: "left", after: "raw>normalized", cycle: 4.5, offset: 6 }],
      ["st-origin", "raw", { spark: false }],
      ["st-normalize", "normalized", { spark: false }],
      ["st-public", "public", { spark: false }],
      ["st-normalize", "st-origin", { back: true, side: "right", delay: 3, cycle: 4.5 }],
      ["st-public", "st-normalize", { back: true, side: "right", delay: 2.2, cycle: 4.5, offset: 6 }],
      ["receiver", "st-public", { back: true, side: "right", delay: 1.4, cycle: 4.5, offset: 12 }]
    ]
  };

  function drawEdges(host, kind) {
    var nodes = {}, all = [];
    var found = host.querySelectorAll("[data-flow-id]");
    var layer = new Layer(host);
    for (var i = 0; i < found.length; i++) {
      var b = layer.box(found[i]);
      nodes[found[i].getAttribute("data-flow-id")] = b;
      all.push(b);
    }
    // An edge with `after` leaves when the named edge's point lands.
    var landed = {};
    (EDGES[kind] || []).forEach(function (edge) {
      var a = nodes[edge[0]], b = nodes[edge[1]], opts = edge[2] || {};
      if (!a || !b) return;
      var others = all.filter(function (o) { return o !== a && o !== b; });
      var points = route(a, b, others, opts.side, opts.offset);
      if (opts.after && landed[opts.after] != null) {
        opts = Object.assign({}, opts, { delay: landed[opts.after] });
      }
      landed[edge[0] + ">" + edge[1]] = (opts.delay || 0) + travelTime(points, opts);
      layer.edge(points, opts);
    });
    // Place step labels at the middle of the edge they name.
    var labels = host.querySelectorAll("[data-flow-label]");
    for (var k = 0; k < labels.length; k++) {
      var pair = labels[k].getAttribute("data-flow-label").split(">");
      var from = nodes[pair[0]], to = nodes[pair[1]];
      if (!from || !to) continue;
      var beside = to.l >= from.r - 2;
      labels[k].classList.toggle("is-beside", beside);
      // Coordinates are host-relative; the label is positioned in its own
      // containing block, so subtract that block's offset within the host.
      var parent = labels[k].offsetParent || host;
      var shift = beside ? layer.box(parent) : { l: 0, t: 0 };
      labels[k].style.left = beside ? (from.r + to.l) / 2 - shift.l + "px" : "";
      labels[k].style.top = beside ? Math.min(from.cy, to.cy) - shift.t + "px" : "";
    }
  }

  /*
   * In place: every step is one command (cmd-N) and one statement (st-N).
   * Wide, the table sits between them: commands enter its left edge and
   * exports leave its right edge, each through a lane in its own gap.
   * Stacked, commands climb the left gutter to the table's left edge and
   * exports descend the right gutter. Back edges between statements run
   * down the outer lane on the side the exports do not use. One step lasts
   * STEP seconds, matching the ip-* keyframes in v02.css, and the layer's
   * clock is set to the document's so a redraw never restarts the cycle out
   * of step with CSS.
   */
  var STEP = 5;
  function drawInplace(host) {
    var layer = new Layer(host);
    var db = host.querySelector('[data-flow-id="db"]');
    if (!db) return;
    var D = layer.box(db);
    var steps = [];
    for (var n = 1; ; n++) {
      var cmd = host.querySelector('[data-flow-id="cmd-' + n + '"]');
      var st = host.querySelector('[data-flow-id="st-' + n + '"]');
      if (!cmd || !st) break;
      steps.push({ C: layer.box(cmd), S: layer.box(st) });
    }
    if (!steps.length) return;
    var cycle = STEP * steps.length;
    function opts(extra) {
      var o = { cycle: cycle, speed: 150 };
      for (var k in extra) o[k] = extra[k];
      return o;
    }
    var beside = D.l >= steps[0].C.r - 2;
    var laneIn = (Math.max.apply(null, steps.map(function (s) { return s.C.r; })) + D.l) / 2;
    var laneOut = (D.r + Math.min.apply(null, steps.map(function (s) { return s.S.l; }))) / 2;
    var left = Math.min.apply(null, [D.l].concat(steps.map(function (s) { return s.C.l; }))) - 14;
    var right = Math.max.apply(null, [D.r].concat(steps.map(function (s) { return s.S.r; }))) + 14;
    steps.forEach(function (step, i) {
      var C = step.C, S = step.S, t = i * STEP;
      if (beside) {
        layer.edge([[C.r, C.cy], [laneIn, C.cy], [laneIn, D.cy], [D.l, D.cy]], opts({ delay: t + 0.2 }));
        layer.edge([[D.r, D.cy], [laneOut, D.cy], [laneOut, S.cy], [S.l, S.cy]], opts({ delay: t + 1.9 }));
      } else {
        layer.edge([[C.l, C.cy], [left, C.cy], [left, D.cy], [D.l, D.cy]], opts({ delay: t + 0.2 }));
        layer.edge([[D.r, D.cy], [right, D.cy], [right, S.cy], [S.r, S.cy]], opts({ delay: t + 1.9 }));
      }
      if (i === 0) return;
      var P = steps[i - 1].S, pts;
      if (beside) {
        pts = [[S.r, S.cy], [right, S.cy], [right, P.cy], [P.r, P.cy]];
      } else {
        var y1 = S.cy + 10, y2 = P.cy + 10;
        pts = [[S.l, y1], [left - 12, y1], [left - 12, y2], [P.l, y2]];
      }
      layer.edge(pts, opts({ back: true, delay: t + 3.2 }));
    });
    var timeline = document.timeline;
    if (layer.svg.setCurrentTime && timeline && timeline.currentTime != null) {
      layer.svg.setCurrentTime((timeline.currentTime / 1000) % cycle);
    }
  }

  function draw(host) {
    var kind = host.getAttribute("data-flow");
    if (kind === "chain") drawChain(host);
    else if (kind === "spread") drawSpread(host);
    else if (kind === "inplace") drawInplace(host);
    else drawEdges(host, kind);
  }

  function init() {
    var hosts = document.querySelectorAll("[data-flow]");
    Array.prototype.forEach.call(hosts, function (host) {
      host.classList.add("flow", "is-drawn");
      var frame = 0, lastWidth = -1, lastHeight = -1;
      function schedule() {
        if (frame) return;
        frame = window.requestAnimationFrame(function () {
          frame = 0;
          var r = host.getBoundingClientRect();
          if (Math.abs(r.width - lastWidth) < 1 && Math.abs(r.height - lastHeight) < 1) return;
          lastWidth = r.width; lastHeight = r.height;
          draw(host);
        });
      }
      if (window.ResizeObserver) new ResizeObserver(schedule).observe(host);
      else window.addEventListener("resize", schedule);
      schedule();
    });
    if (motion && motion.addEventListener) {
      motion.addEventListener("change", function () {
        Array.prototype.forEach.call(hosts, draw);
      });
    }
    // Web fonts change box heights after first layout.
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { Array.prototype.forEach.call(hosts, draw); });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
