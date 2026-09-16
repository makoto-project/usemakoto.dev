/*
 * Theme: light for every visitor unless they chose dark with the toggle.
 *
 * Loaded blocking in <head>, directly after the stylesheet, so the attribute
 * is set before first paint and a dark choice never flashes light. The OS
 * colour-scheme preference is deliberately ignored. Storage can be missing or
 * throw (private windows, blocked site data); the page then stays light and
 * the toggle still works for the current page view.
 *
 * After parsing it adds the toggle to the top bar and gives stacked tables
 * their column labels (data-label on each cell, read by the narrow-width CSS).
 */
(function () {
  "use strict";

  var KEY = "makoto-theme";
  var root = document.documentElement;

  function stored() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function store(value) {
    try { window.localStorage.setItem(KEY, value); } catch (e) { /* not persisted */ }
  }
  function apply(theme) {
    root.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
  }

  apply(stored());

  var ICON = '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">' +
    '<circle class="theme-sun" cx="10" cy="10" r="3.6"/>' +
    '<g class="theme-rays"><path d="M10 1.8v2.1M10 16.1v2.1M1.8 10h2.1M16.1 10h2.1M4.2 4.2l1.5 1.5M14.3 14.3l1.5 1.5M4.2 15.8l1.5-1.5M14.3 5.7l1.5-1.5"/></g>' +
    '<path class="theme-moon" d="M15.6 12.6A6.4 6.4 0 0 1 7.4 4.4a6.4 6.4 0 1 0 8.2 8.2Z"/>' +
    "</svg>";

  function addToggle() {
    var bar = document.querySelector(".topbar-inner");
    if (!bar || bar.querySelector(".theme-toggle")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "theme-toggle";
    // Constant name, state in aria-pressed: "Dark theme, toggle button, pressed".
    button.innerHTML = ICON + '<span class="visually-hidden">Dark theme</span>';
    function sync() {
      var dark = root.getAttribute("data-theme") === "dark";
      button.setAttribute("aria-pressed", dark ? "true" : "false");
      button.title = dark ? "Switch to light theme" : "Switch to dark theme";
    }
    button.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      store(next);
      sync();
      document.dispatchEvent(new CustomEvent("makoto:theme", { detail: next }));
    });
    sync();
    var menu = bar.querySelector(".mobile-menu");
    bar.insertBefore(button, menu);
  }

  function labelTables() {
    var tables = document.querySelectorAll("main table");
    for (var t = 0; t < tables.length; t++) {
      var heads = tables[t].querySelectorAll("thead th");
      if (!heads.length) continue;
      var rows = tables[t].querySelectorAll("tbody tr");
      for (var r = 0; r < rows.length; r++) {
        var cells = rows[r].children;
        for (var c = 0; c < cells.length && c < heads.length; c++) {
          if (!cells[c].hasAttribute("data-label")) {
            cells[c].setAttribute("data-label", heads[c].textContent.replace(/\s+/g, " ").trim());
          }
        }
      }
    }
  }

  function ready() { addToggle(); labelTables(); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
