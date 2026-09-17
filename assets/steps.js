/*
 * Step index for the example walkthroughs.
 *
 * The page ships a plain list of in-page anchors. This script makes it stick
 * under the top bar while the steps scroll past and marks the step in view.
 * An index too long for one line keeps every number but shows only the
 * current step's label (the first step's, before any is current). That is
 * decided by width alone, never by scroll position: a sticky element keeps its
 * place in the flow, so changing its height mid-scroll would move the page.
 * Anchored steps clear the top bar and the index (--step-index-h).
 */
(function () {
  "use strict";

  var track = document.querySelector("[data-step-track]");
  var nav = track && track.querySelector("[data-step-index]");
  if (!nav || !("IntersectionObserver" in window)) return;

  var items = [];
  Array.prototype.forEach.call(nav.querySelectorAll("a[href^='#']"), function (link) {
    var target = document.getElementById(link.getAttribute("href").slice(1));
    if (target) items.push({ link: link, item: link.parentElement, target: target });
  });
  if (!items.length) return;

  // A pair's statement step belongs to the index entry of the data step before it.
  var steps = [];
  items.forEach(function (entry, index) {
    var li = entry.target;
    var until = items[index + 1] ? items[index + 1].target : null;
    while (li && li !== until) {
      if (li.tagName === "LI") steps.push({ el: li, entry: entry });
      li = li.nextElementSibling;
    }
  });

  var current = null;
  var visible = [];

  function topbarHeight() {
    var value = getComputedStyle(document.documentElement).getPropertyValue("--topbar-height");
    return parseFloat(value) || 64;
  }

  function measure() {
    nav.classList.remove("is-compact");
    var first = items[0].item.offsetTop;
    var wraps = items.some(function (entry) { return entry.item.offsetTop !== first; });
    nav.classList.toggle("is-compact", wraps);
    track.style.setProperty("--step-index-h", nav.offsetHeight + "px");
  }

  function mark(entry) {
    if (entry === current) return;
    current = entry;
    items.forEach(function (other, index) {
      var on = other === entry;
      if (on) other.link.setAttribute("aria-current", "step"); else other.link.removeAttribute("aria-current");
      other.item.classList.toggle("is-current", on || (!entry && index === 0));
    });
  }

  var stepObserver;

  function observe() {
    if (stepObserver) stepObserver.disconnect();
    var top = topbarHeight();

    // The current step is the last one crossing the band under the index: the
    // step before it may still reach the band with its bottom padding.
    var offset = Math.round(top + (parseFloat(track.style.getPropertyValue("--step-index-h")) || 0) + 8);
    visible = [];
    stepObserver = new IntersectionObserver(function (records) {
      records.forEach(function (record) {
        var step = steps.filter(function (s) { return s.el === record.target; })[0];
        var at = visible.indexOf(step);
        if (record.isIntersecting && at === -1) visible.push(step);
        if (!record.isIntersecting && at !== -1) visible.splice(at, 1);
      });
      if (visible.length) {
        visible.sort(function (a, b) { return steps.indexOf(a) - steps.indexOf(b); });
        mark(visible[visible.length - 1].entry);
      } else if (steps[0].el.getBoundingClientRect().top > offset) {
        mark(null);
      }
    }, { rootMargin: "-" + offset + "px 0px -55% 0px" });
    steps.forEach(function (step) { stepObserver.observe(step.el); });
  }

  nav.classList.add("is-live");
  items[0].item.classList.add("is-current");
  measure();
  observe();

  // A deep link to a step jumps before code frames and fonts finish growing
  // the page above it. Land it again once they have, unless the reader has
  // already started moving.
  var linked = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (linked && track.contains(linked) && document.readyState !== "complete") {
    var moved = false;
    var stop = function () { moved = true; };
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (type) {
      window.addEventListener(type, stop, { once: true, passive: true });
    });
    window.addEventListener("load", function () {
      if (!moved) linked.scrollIntoView({ block: "start", behavior: "instant" });
    });
  }

  var pending = 0;
  window.addEventListener("resize", function () {
    window.clearTimeout(pending);
    pending = window.setTimeout(function () { measure(); observe(); }, 120);
  });
})();
