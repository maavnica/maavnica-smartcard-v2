/**
 * Consentement cookies / mesure d’audience — Maavnica SmartCard (vanilla, sans dépendance).
 * localStorage.maavnica_consent : "all" | "essential"
 */
(function () {
  var STORAGE_KEY = "maavnica_consent";
  var BANNER_ID = "maavnica-consent-banner";

  window.maavnicaConsentAllowsAnalytics = function () {
    try {
      return localStorage.getItem(STORAGE_KEY) === "all";
    } catch (e) {
      return false;
    }
  };

  function notifyConsentUpdate() {
    try {
      document.dispatchEvent(new CustomEvent("maavnica-consent-updated"));
    } catch (e) {}
  }

  function hideBanner() {
    var el = document.getElementById(BANNER_ID);
    if (el) el.remove();
    document.documentElement.style.paddingBottom = "";
  }

  function setConsent(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {}
    hideBanner();
    notifyConsentUpdate();
  }

  function injectStyles() {
    if (document.getElementById("maavnica-consent-styles")) return;
    var s = document.createElement("style");
    s.id = "maavnica-consent-styles";
    s.textContent =
      "#" +
      BANNER_ID +
      "{position:fixed;left:0;right:0;bottom:0;z-index:9999;padding:12px 14px calc(12px + env(safe-area-inset-bottom,0px));" +
      "background:rgba(2,6,23,.96);border-top:1px solid rgba(148,163,184,.35);box-shadow:0 -8px 32px rgba(0,0,0,.45);font-family:system-ui,-apple-system,Segoe UI,sans-serif;}" +
      "#" +
      BANNER_ID +
      " .mcb-inner{max-width:900px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;}" +
      "#" +
      BANNER_ID +
      " .mcb-text{flex:1 1 220px;font-size:12px;line-height:1.45;color:#cbd5e1;margin:0;}" +
      "#" +
      BANNER_ID +
      " .mcb-text a{color:#93c5fd;text-underline-offset:3px;}" +
      "#" +
      BANNER_ID +
      " .mcb-actions{display:flex;flex-wrap:wrap;gap:8px;flex:0 0 auto;}" +
      "#" +
      BANNER_ID +
      " .mcb-btn{border-radius:999px;padding:8px 14px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid rgba(148,163,184,.4);}" +
      "#" +
      BANNER_ID +
      " .mcb-btn--ghost{background:transparent;color:#e5e7eb;}" +
      "#" +
      BANNER_ID +
      " .mcb-btn--ghost:hover{border-color:rgba(148,163,184,.65);}" +
      "#" +
      BANNER_ID +
      " .mcb-btn--primary{background:#facc15;color:#020617;border-color:#facc15;}" +
      "#" +
      BANNER_ID +
      " .mcb-btn--primary:hover{opacity:.92;}" +
      "@media(max-width:520px){#" +
      BANNER_ID +
      " .mcb-actions{width:100%;}#" +
      BANNER_ID +
      " .mcb-btn{flex:1 1 auto;text-align:center;min-width:0;}}";
    document.head.appendChild(s);
  }

  function showBanner() {
    if (document.getElementById(BANNER_ID)) return;
    injectStyles();
    var bar = document.createElement("div");
    bar.id = BANNER_ID;
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", "Choix cookies et mesure d’audience");
    bar.innerHTML =
      '<div class="mcb-inner">' +
      '<p class="mcb-text">Nous utilisons une <strong>mesure d’audience interne</strong> (pages vues, clics) pour améliorer SmartCard. Aucun publicitaire tiers. ' +
      '<a href="/static/cookies.html">En savoir plus</a></p>' +
      '<div class="mcb-actions">' +
      '<button type="button" class="mcb-btn mcb-btn--ghost" data-maavnica-consent="essential">Continuer sans mesure</button>' +
      '<button type="button" class="mcb-btn mcb-btn--primary" data-maavnica-consent="all">Accepter</button>' +
      "</div></div>";
    bar.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t || !t.getAttribute) return;
      var v = t.getAttribute("data-maavnica-consent");
      if (v === "essential" || v === "all") setConsent(v);
    });
    document.body.appendChild(bar);
    document.documentElement.style.paddingBottom = "72px";
  }

  window.maavnicaRunSiteAnalyticsInit = function (opts) {
    function run() {
      if (!window.maavnicaConsentAllowsAnalytics()) return;
      var SA = window.maavnicaSiteAnalytics;
      if (SA && typeof SA.init === "function") SA.init(opts || {});
    }
    run();
    document.addEventListener("maavnica-consent-updated", run);
  };

  try {
    if (!localStorage.getItem(STORAGE_KEY)) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", showBanner);
      } else {
        showBanner();
      }
    }
  } catch (e) {
    showBanner();
  }
})();
