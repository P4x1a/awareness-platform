// Micro-interacoes da plataforma: contagem animada, barras de progresso e
// medidor circular (anel). Sem dependencias externas.
(function () {
  "use strict";

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fmt(v, decimals) {
    return decimals ? v.toFixed(decimals) : String(Math.round(v));
  }

  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count")) || 0;
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    if (reduce || target === 0) { el.textContent = fmt(target, decimals); return; }
    var dur = 900, start = null;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased, decimals);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function animateRing(el) {
    var r = parseFloat(el.getAttribute("r")) || 52;
    var c = 2 * Math.PI * r;
    var pct = Math.max(0, Math.min(100, parseFloat(el.getAttribute("data-ring")) || 0));
    el.style.strokeDasharray = c.toFixed(1);
    el.style.strokeDashoffset = c.toFixed(1);  // comeca vazio
    requestAnimationFrame(function () {
      el.style.strokeDashoffset = (c * (1 - pct / 100)).toFixed(1);
    });
  }

  function run() {
    document.querySelectorAll("[data-count]").forEach(animateCount);
    document.querySelectorAll(".ring-fg[data-ring]").forEach(animateRing);
    requestAnimationFrame(function () {
      document.querySelectorAll(".rate-fill[data-rate]").forEach(function (el) {
        var r = parseFloat(el.getAttribute("data-rate")) || 0;
        el.style.width = Math.max(0, Math.min(100, r)) + "%";
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
