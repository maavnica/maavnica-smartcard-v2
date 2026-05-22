/**
 * Analytics site / landing Maavnica — envoi non bloquant vers POST /api/site-analytics/event
 * Filtre interne : ?admin_view=1 ou localStorage maavnica_internal_view = "1"
 * Consentement : localStorage maavnica_consent === "essential" ou absent → pas d’analytics
 */
(function () {
  var ENDPOINT_PATH = "/api/site-analytics/event";
  var STORAGE_VISITOR = "maavnica_site_vid";
  var STORAGE_INTERNAL = "maavnica_internal_view";
  var STORAGE_CONSENT = "maavnica_consent";

  function shouldSkip() {
    try {
      var consent = localStorage.getItem(STORAGE_CONSENT);
      if (consent !== "all") return true;
      var p = new URLSearchParams(window.location.search);
      if (p.get("admin_view") === "1") return true;
      if (localStorage.getItem(STORAGE_INTERNAL) === "1") return true;
    } catch (e) {
      return true;
    }
    return false;
  }

  function apiBase() {
    var h = window.location.hostname || "";
    if (
      h === "smartcard.maavnica.com" ||
      h === "localhost" ||
      h === "127.0.0.1"
    ) {
      return "";
    }
    return "https://smartcard.maavnica.com";
  }

  function getOrCreateVisitorId() {
    try {
      var v = localStorage.getItem(STORAGE_VISITOR);
      if (v) return v;
      v =
        "v_" +
        Math.random().toString(36).slice(2) +
        Date.now().toString(36);
      localStorage.setItem(STORAGE_VISITOR, v);
      return v;
    } catch (e) {
      return null;
    }
  }

  function captureAttribution() {
    var p = new URLSearchParams(window.location.search);
    return {
      source: p.get("src") || p.get("source") || null,
      referrer: document.referrer || null,
      utm_source: p.get("utm_source"),
      utm_medium: p.get("utm_medium"),
      utm_campaign: p.get("utm_campaign"),
    };
  }

  function currentLang() {
    var p = new URLSearchParams(window.location.search);
    var q = (p.get("lang") || "").toLowerCase();
    if (q === "es" || q === "fr") return q;
    try {
      var ls = localStorage.getItem("maavnica_lang");
      if (ls === "es" || ls === "fr") return ls;
    } catch (e) {}
    var h = (document.documentElement.lang || "fr").slice(0, 2).toLowerCase();
    return h === "es" ? "es" : "fr";
  }

  function sendPayload(body) {
    if (shouldSkip()) return;
    var url = apiBase() + ENDPOINT_PATH;
    var json = JSON.stringify(body);
    try {
      if (navigator.sendBeacon) {
        var blob = new Blob([json], { type: "application/json" });
        if (navigator.sendBeacon(url, blob)) return;
      }
    } catch (e1) {}
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: json,
      keepalive: true,
      credentials: "omit",
    }).catch(function () {});
  }

  function buildBody(opts) {
    var att = captureAttribution();
    var path =
      window.location.pathname +
      (window.location.search || "");
    if (path.length > 1024) path = path.slice(0, 1024);
    return {
      domain: window.location.hostname || "unknown",
      path: path,
      page_type: opts.page_type || "other",
      event_type: opts.event_type,
      source: att.source,
      referrer: att.referrer,
      utm_source: att.utm_source,
      utm_medium: att.utm_medium,
      utm_campaign: att.utm_campaign,
      lang: opts.lang != null ? opts.lang : currentLang(),
      target:
        opts.target != null ? String(opts.target).slice(0, 512) : null,
      visitor_id: getOrCreateVisitorId(),
    };
  }

  var scrollBound = false;

  window.maavnicaSiteAnalytics = {
    track: function (opts) {
      if (!opts || !opts.event_type) return;
      sendPayload(buildBody(opts));
    },
    init: function (opts) {
      opts = opts || {};
      var pt = opts.page_type || opts.pageType || "other";
      this.track({ event_type: "page_view", page_type: pt });
      if (opts.bindScroll === false) return;
      if (scrollBound) return;
      scrollBound = true;
      var s50 = false;
      var s90 = false;
      function onScroll() {
        var doc = document.documentElement;
        var h = doc.scrollHeight - doc.clientHeight;
        if (h <= 0) return;
        var p = doc.scrollTop / h;
        if (!s50 && p >= 0.5) {
          s50 = true;
          window.maavnicaSiteAnalytics.track({
            event_type: "scroll_50",
            page_type: pt,
          });
        }
        if (!s90 && p >= 0.9) {
          s90 = true;
          window.maavnicaSiteAnalytics.track({
            event_type: "scroll_90",
            page_type: pt,
          });
        }
        if (s50 && s90) {
          window.removeEventListener("scroll", onScroll);
        }
      }
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    },
  };
})();
