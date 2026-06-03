/* SmartCard FR — runtime partagé (analytics, CTA, formulaires, QR, reco, vCard) */
    /**
     * TODO(analytics): Les données déjà comptabilisées avant ce correctif peuvent rester polluées.
     * Le filtrage isInternalView s’applique à partir du déploiement du patch (aucune purge auto côté client).
     */
    const INTERNAL_CARDS_LS_KEY = "maavnica_internal_cards";
    const INTERNAL_MODE_LS_KEY = "maavnica_internal_mode";
    const baseUrl = window.location.origin || "";

    var ALLOWED_VISUAL_THEMES = new Set([
      "wellness-soft",
      "wellness-soft-minimal",
      "artisan",
      "real-estate",
      "corporate",
      "maavnica",
    ]);

    function isWellnessVisualTheme() {
      var t = document.body.getAttribute("data-theme");
      return t === "wellness-soft" || t === "wellness-soft-minimal";
    }

    /** Portrait centré + ville sous le métier (wellness & artisan premium). */
    function isPortraitHeroTheme() {
      var t = document.body.getAttribute("data-theme");
      return isWellnessVisualTheme() || t === "artisan";
    }

    function isWellnessMinimalTheme() {
      return document.body.getAttribute("data-theme") === "wellness-soft-minimal";
    }

    function openWellnessContactModal() {
      var modal = document.getElementById("wellness-contact-modal");
      if (!modal) return;
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      document.body.classList.add("wellness-quote-modal-open");
      var first = document.getElementById("quote-name");
      if (first) {
        window.setTimeout(function () {
          first.focus();
        }, 60);
      }
    }

    function closeWellnessContactModal() {
      var modal = document.getElementById("wellness-contact-modal");
      if (!modal) return;
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      document.body.classList.remove("wellness-quote-modal-open");
    }

    function initWellnessMinimalQuoteModal() {
      if (!isWellnessMinimalTheme()) return;
      var modal = document.getElementById("wellness-contact-modal");
      var host = document.getElementById("wellness-contact-modal-host");
      var panel = document.getElementById("panel-quote");
      if (!modal || !host || !panel || modal.getAttribute("data-wellness-init") === "1") return;
      modal.setAttribute("data-wellness-init", "1");
      host.appendChild(panel);
      modal.querySelectorAll("[data-wellness-contact-close]").forEach(function (el) {
        el.addEventListener("click", function (e) {
          e.preventDefault();
          closeWellnessContactModal();
        });
      });
      if (!modal.getAttribute("data-wellness-esc-bound")) {
        modal.setAttribute("data-wellness-esc-bound", "1");
        document.addEventListener("keydown", function (e) {
          if (e.key === "Escape" && modal.classList.contains("is-open")) {
            closeWellnessContactModal();
          }
        });
      }
    }

    /** Aligne body[data-theme] sur card.visual_theme (SSR + API, dont wellness-soft-minimal). */
    function applyVisualThemeFromCard(card) {
      if (!/^\/c\/[^/]+/i.test(window.location.pathname || "")) return;
      var vt = card && card.visual_theme != null ? String(card.visual_theme).trim().toLowerCase() : "";
      if (!vt || !ALLOWED_VISUAL_THEMES.has(vt)) return;
      document.body.setAttribute("data-theme", vt);
    }

    function deviceInternalModeActive() {
      try {
        return localStorage.getItem(INTERNAL_MODE_LS_KEY) === "1";
      } catch (e) {
        return false;
      }
    }

    function getSlugFromPath() {
      const parts = window.location.pathname.split("/").filter(Boolean);
      const cIndex = parts.indexOf("c");
      if (cIndex !== -1 && parts[cIndex + 1]) {
        return decodeURIComponent(parts[cIndex + 1]);
      }
      return null;
    }

    function internalSlugStorageKey(slug) {
      const s = (slug || "").trim().toLowerCase();
      return s || "";
    }

    function getInternalSlugsMap() {
      try {
        const raw = localStorage.getItem(INTERNAL_CARDS_LS_KEY);
        if (!raw) return {};
        const o = JSON.parse(raw);
        return o !== null && typeof o === "object" && !Array.isArray(o) ? o : {};
      } catch (e) {
        return {};
      }
    }

    function markSlugAsInternal(slug) {
      const key = internalSlugStorageKey(slug);
      if (!key) return;
      try {
        const m = getInternalSlugsMap();
        m[key] = true;
        localStorage.setItem(INTERNAL_CARDS_LS_KEY, JSON.stringify(m));
      } catch (e) {}
    }

    function unmarkSlugInternal(slug) {
      const key = internalSlugStorageKey(slug);
      if (!key) return;
      try {
        const m = getInternalSlugsMap();
        delete m[key];
        localStorage.setItem(INTERNAL_CARDS_LS_KEY, JSON.stringify(m));
      } catch (e) {}
    }

    function isSlugMarkedInternal(slug) {
      const key = internalSlugStorageKey(slug);
      if (!key) return false;
      return !!getInternalSlugsMap()[key];
    }

    function urlHasAdminViewFlag() {
      try {
        return new URLSearchParams(window.location.search || "").get("admin_view") === "1";
      } catch (e) {
        return false;
      }
    }

    /** True si la page est une consultation interne (param URL ou slug marqué localement pour ce navigateur). */
    let isInternalView = false;

    function migrateLegacyAdminViewFlag(slug) {
      try {
        if (localStorage.getItem("smartcard_admin_view") === "1" && slug) {
          markSlugAsInternal(slug);
          localStorage.removeItem("smartcard_admin_view");
        }
      } catch (e) {}
    }

    function refreshIsInternalView(slug) {
      migrateLegacyAdminViewFlag(slug);
      isInternalView =
        deviceInternalModeActive() ||
        urlHasAdminViewFlag() ||
        !!(slug && isSlugMarkedInternal(slug));
      const badge = document.getElementById("admin-preview-badge");
      if (badge) {
        badge.hidden = !isInternalView;
      }
    }

    function shouldTrackAnalytics() {
      if (isInternalView) return false;
      try {
        if (localStorage.getItem("maavnica_consent") !== "all") return false;
      } catch (e) {
        return false;
      }
      return true;
    }

    function syncInternalViewFromUrl(slug) {
      try {
        const p = new URLSearchParams(window.location.search || "");
        if (p.get("admin_view") === "1") {
          if (slug) markSlugAsInternal(slug);
          localStorage.setItem(INTERNAL_MODE_LS_KEY, "1");
        }
        if (p.get("admin_view") === "0") {
          if (slug) unmarkSlugInternal(slug);
          localStorage.removeItem(INTERNAL_MODE_LS_KEY);
        }
      } catch (e) {}
    }

    /** URL publique canonique sans query (partage, QR, textes clients). */
    function getPublicCardUrl(slug) {
      if (!slug) return "";
      return `${baseUrl}/c/${encodeURIComponent(slug)}`;
    }

    /** Carte marketing / démo : slug commence par « demo » (ex. demo, demo2, demo-artisan). */
    function isDemoSlug(slug) {
      if (!slug) return false;
      return slug.toLowerCase().startsWith("demo");
    }

    /** Démos LATAM (servies par index_latam en prod) — pas de surcouche SEO FR sur ce préfixe. */
    function isLatamDemoSlugPrefix(slug) {
      return !!(slug && String(slug).trim().toLowerCase().startsWith("demo-latam-"));
    }

    function upsertHeadMeta(attr, key, content) {
      if (content === undefined || content === null) return;
      const sel = 'meta[' + attr + '="' + key.replace(/"/g, '\\"') + '"]';
      var el = document.head.querySelector(sel);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, key);
        document.head.appendChild(el);
      }
      el.setAttribute("content", String(content));
    }

    /** Aligné sur le SSR Python (_fr_public_card_seo_strings) pour éviter toute contradiction crawler/client. */
    function absoluteUrlForOg(u) {
      var s = (u || "").trim();
      if (!s) return "";
      if (/^https?:\/\//i.test(s)) return s;
      if (s.indexOf("//") === 0) return (window.location.protocol || "https:") + s;
      if (s.indexOf("/") === 0) return String(baseUrl).replace(/\/?$/, "") + s;
      return String(baseUrl).replace(/\/?$/, "") + "/" + s;
    }

    /**
     * Métadonnées SEO (title, meta, Open Graph) + H1 hors écran pour les cartes FR (index.html).
     * Données : champs API existants ; ville optionnelle si ajoutée plus tard (city / service_city).
     */
    function updateFrenchCardSeo(card, slug, resolvedDisplayName) {
      if (!card || !slug || isLatamDemoSlugPrefix(slug)) return;

      const name =
        (resolvedDisplayName != null && String(resolvedDisplayName).trim()) ||
        (card.display_name != null && String(card.display_name).trim()) ||
        (card.company_name != null && String(card.company_name).trim()) ||
        "";
      const job = (card.job_title != null && String(card.job_title).trim()) || "";
      const city =
        (card.city != null && String(card.city).trim()) ||
        (card.service_city != null && String(card.service_city).trim()) ||
        "";

      const fallbackTitle = "Carte professionnelle | Maavnica";
      let pageTitle = fallbackTitle;
      if (job && city && name) pageTitle = job + " à " + city + " | " + name;
      else if (job && name) pageTitle = job + " | " + name;
      else if (name) pageTitle = name + " | Maavnica";
      document.title = pageTitle;

      let metaDesc = "";
      if (name && job && city) {
        metaDesc =
          name + ", " + job + " à " + city + ". Contact rapide, avis clients et recommandations.";
      } else if (name && job) {
        metaDesc =
          name +
          ", " +
          job +
          ". Contact rapide, avis clients et recommandations.";
      } else if (name && city) {
        metaDesc =
          name +
          " à " +
          city +
          ". Contact rapide, avis clients et recommandations.";
      } else if (name) {
        metaDesc =
          name + ". Contact rapide, avis clients et recommandations.";
      } else {
        metaDesc =
          "Carte professionnelle Maavnica. Contact rapide, avis clients et recommandations.";
      }

      let ogTitle = "";
      if (job && city && name) {
        ogTitle = job + " à " + city + " recommandé par ses clients | " + name;
      } else if (job && name) {
        ogTitle = job + " recommandé par ses clients | " + name;
      } else if (name && city) {
        ogTitle = name + " | Maavnica";
      } else if (name) {
        ogTitle = name + " | Maavnica";
      } else {
        ogTitle = "Maavnica SmartCard";
      }

      const ogDesc =
        name !== ""
          ? "Découvrez " + name + ". Contact direct, avis clients et recommandation simplifiée."
          : "Découvrez cette carte professionnelle. Contact direct, avis clients et recommandation simplifiée.";

      upsertHeadMeta("name", "description", metaDesc);
      upsertHeadMeta("property", "og:title", ogTitle);
      upsertHeadMeta("property", "og:description", ogDesc);
      upsertHeadMeta("property", "og:url", getPublicCardUrl(slug));
      upsertHeadMeta("name", "twitter:card", "summary_large_image");
      upsertHeadMeta("name", "twitter:title", ogTitle);
      upsertHeadMeta("name", "twitter:description", ogDesc);

      var canon = document.querySelector('link[rel="canonical"]');
      if (canon) canon.setAttribute("href", getPublicCardUrl(slug));

      var h1 = document.getElementById("public-card-seo-h1");
      if (h1) {
        if (name && job && city) h1.textContent = name + " — " + job + " à " + city;
        else if (name && job) h1.textContent = name + " — " + job;
        else if (name) h1.textContent = name;
        else h1.textContent = "Carte professionnelle Maavnica";
      }
    }

    /**
     * Image Open Graph pour les partages (réseaux / messageries) — cartes FR seulement (pas demo-latam-*).
     */
    function updateFrenchCardOgImage(card, slug) {
      if (!slug || isLatamDemoSlugPrefix(slug)) return;
      var el = document.getElementById("seo-og-image");
      if (!el) return;
      var defaultImage = `${baseUrl}/static/og-default.jpg?v=2`;
      var raw = "";
      if (card && card.avatar_url != null) raw = String(card.avatar_url).trim();
      else if (card && card.photo_url != null) raw = String(card.photo_url).trim();
      var url;
      if (String(slug).trim().toLowerCase() === "arnaud-huard") {
        url = `${baseUrl}/static/og-arnaud-huard.jpg`;
      } else {
        url = raw ? absoluteUrlForOg(raw) : defaultImage;
      }
      el.setAttribute("content", url);
      upsertHeadMeta("name", "twitter:image", url);
    }

    /** Clé mode propriétaire : /c/{slug}?o=… (ne pas inclure dans les SMS / mails clients). */
    function getOwnerShareKeyFromUrl() {
      try {
        var p = new URLSearchParams(window.location.search || "");
        var v = (p.get("o") || "").trim();
        return v || null;
      } catch (e) {
        return null;
      }
    }

    /** Masque les textes pédagogiques du bloc central sur les cartes client uniquement. */
    function applyClientMidsectionVisibility(isDemoCard) {
      const ids = [
        "left-block-sub",
        "left-block-tags-hint",
        "contact-actions-guide",
        "pill-section-hint",
        "hint-share-signature",
        "hint-post-prestation",
      ];
      ids.forEach(function (id) {
        const el = document.getElementById(id);
        if (!el) return;
        if (isDemoCard) {
          el.style.removeProperty("display");
        } else {
          el.style.display = "none";
        }
      });

    }

    function applyPublicShellCopy(isDemoCard, companyName, fullName) {
      const sb = document.getElementById("status-bar-label");
      const subline = document.getElementById("hero-subline");
      const foot = document.getElementById("public-card-footer");
      const tagRow = document.getElementById("hero-tagline-row");
      const tagMeta = document.getElementById("hero-tagline");
      const qrImg = document.getElementById("qr-image");

      if (isDemoCard) {
        if (sb) sb.textContent = "Maavnica SmartCard";
        if (subline) subline.textContent = "MAAVNICA SMARTCARD";
        if (foot) {
          foot.innerHTML =
            'SmartCard Maavnica · <a href="https://maavnica.com" target="_blank" rel="noopener noreferrer">En savoir plus</a>';
        }
        if (tagRow) tagRow.style.display = "";
        if (tagMeta) tagMeta.textContent = "via Maavnica SmartCard";
        document.title = "Maavnica SmartCard – Carte publique";
        if (qrImg) qrImg.alt = qrImg.getAttribute("data-alt-demo") || qrImg.alt;
        return;
      }

      if (sb) sb.textContent = "Maavnica SmartCard";
      if (subline) subline.textContent = "";
      if (foot) foot.textContent = "Carte de contact professionnelle";
      if (tagRow) tagRow.style.display = "none";
      const dn = ((fullName || "").trim() || (companyName || "").trim() || "Carte de contact");
      document.title = dn + " – Contact";
      if (qrImg) qrImg.alt = qrImg.getAttribute("data-alt-client") || "QR code";
    }

    function getUrlTrackingParams() {
      try {
        const p = new URLSearchParams(window.location.search || "");
        return {
          src: p.get("src") || null,
          ref: p.get("ref") || null,
          rec: p.get("rec") || null,
        };
      } catch (e) {
        return { src: null, ref: null, rec: null };
      }
    }

    function getRecommendationReferrerIdFromUrl() {
      try {
        const p = new URLSearchParams(window.location.search || "");
        const raw = (p.get("r") || "").trim();
        return raw || null;
      } catch (e) {
        return null;
      }
    }

    function getOrCreateRecommendationVisitorId() {
      const key = "smartcard_recommend_visitor_id";
      try {
        const existing = (localStorage.getItem(key) || "").trim();
        if (existing) return existing;
      } catch (e) {}

      const generated = "v_" + Math.random().toString(36).slice(2, 10);
      try {
        localStorage.setItem(key, generated);
      } catch (e) {}
      return generated;
    }

    function trackRecommendationEvent(
      cardSlug,
      eventType,
      referrerId,
      visitorId,
      recommenderFirst,
      recommenderLast
    ) {
      if (!shouldTrackAnalytics()) {
        console.info("[SmartCard analytics] skipped internal recommendation event");
        return;
      }
      if (!cardSlug || !eventType || !referrerId) return;
      var body = {
        card_slug: cardSlug,
        referrer_id: referrerId,
        visitor_id: visitorId || null,
        event_type: eventType,
      };
      if (eventType === "recommend_link_created") {
        body.recommender_first_name = recommenderFirst || null;
        body.recommender_last_name = recommenderLast || null;
      } else {
        if (recommenderFirst) body.recommender_first_name = recommenderFirst;
        if (recommenderLast) body.recommender_last_name = recommenderLast;
      }
      // fetch + Content-Type explicite : sendBeacon + Blob est peu fiable pour le JSON côté API.
      try {
        var json = JSON.stringify(body);
        fetch("/api/analytics/recommendation-event", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: json,
          keepalive: true,
        }).catch(function () {});
      } catch (e) {}
    }

    function sanitizeReferrerId(input) {
      return (input || "")
        .toString()
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, "")
        .slice(0, 64);
    }

    /** True si l’URL contient ?src=recommend (ou &src=recommend) — insensible à la casse. */
    function isRecommendSourceParam() {
      try {
        const v = new URLSearchParams(window.location.search || "").get("src");
        return (v || "").trim().toLowerCase() === "recommend";
      } catch (e) {
        return false;
      }
    }

    function hideRecommendTrustBanner() {
      var trustBanner = document.getElementById("hero-recommend-trust");
      if (!trustBanner) return;
      trustBanner.setAttribute("hidden", "");
      trustBanner.classList.remove("is-visible");
      trustBanner.setAttribute("aria-hidden", "true");
    }

    /**
     * Continuité relationnelle : même bandeau discret pour ?src=recommend et pour ?r=.
     * @param {string|null|undefined} arrivalAttributionFromApi — prénom/nom connus (GET /cards/... ?r=), sinon affinage URL seule.
     */
    function syncRecommendTrustBanner(arrivalAttributionFromApi) {
      var trustBanner = document.getElementById("hero-recommend-trust");
      if (!trustBanner) return;
      var fromSrc = isRecommendSourceParam();
      var rid = getRecommendationReferrerIdFromUrl();
      var fromR = !!(rid && String(rid).trim());
      if (!fromSrc && !fromR) {
        hideRecommendTrustBanner();
        return;
      }
      trustBanner.removeAttribute("hidden");
      trustBanner.classList.add("is-visible");
      trustBanner.setAttribute("aria-hidden", "false");
      var attr =
        arrivalAttributionFromApi != null && arrivalAttributionFromApi !== undefined
          ? String(arrivalAttributionFromApi).trim()
          : "";
      if (attr) {
        var short = attr.length > 44 ? attr.slice(0, 41).trim() + "…" : attr;
        trustBanner.textContent = "👍 " + short + " vous transmet cette carte.";
      } else if (fromR) {
        trustBanner.textContent =
          "👍 Vous arrivez ici suite à une recommandation personnelle.";
      } else {
        trustBanner.textContent = "👍 Ce professionnel vous a été recommandé";
      }
    }

    function postAnalytics(url, body) {
      try {
        const json = JSON.stringify(body);
        if (navigator.sendBeacon) {
          const blob = new Blob([json], { type: "application/json" });
          navigator.sendBeacon(url, blob);
        } else {
          fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: json,
            keepalive: true,
          }).catch(function () {});
        }
      } catch (e) {}
    }

    function trackCardVisit(slug) {
      if (!shouldTrackAnalytics()) {
        console.info("[SmartCard analytics] skipped internal card visit");
        return;
      }
      const t = getUrlTrackingParams();
      postAnalytics("/api/analytics/visit", {
        slug: slug,
        src: t.src,
        ref: t.ref,
        rec: t.rec,
      });
    }

    function trackCardEvent(slug, eventType) {
      if (!shouldTrackAnalytics()) {
        console.info("[SmartCard analytics] skipped internal card event", eventType);
        return;
      }
      const t = getUrlTrackingParams();
      postAnalytics("/api/analytics/event", {
        slug: slug,
        event_type: eventType,
        src: t.src,
        ref: t.ref,
        rec: t.rec,
      });
    }

    function showToast(message, isError = false) {
      const toast = document.getElementById("toast");
      toast.textContent = message;
      toast.classList.toggle("error", isError);
      toast.classList.add("show");
      setTimeout(() => toast.classList.remove("show"), 2600);
    }

    function generateRecommendationToken() {
      var a = Math.random().toString(36).slice(2, 10);
      var b = Math.random().toString(36).slice(2, 6);
      return "rec_" + a + b;
    }

    function readReferrerStorageState(storageKey) {
      try {
        var raw = localStorage.getItem(storageKey);
        if (!raw) return { kind: "empty" };
        var trimmed = raw.trim();
        if (!trimmed) return { kind: "empty" };
        if (trimmed.charAt(0) === "{") {
          var o = JSON.parse(trimmed);
          var id = sanitizeReferrerId(o.referrerId || o.i || "");
          var first = (o.firstName || o.f || "").trim();
          var last = (o.lastName || o.l || "").trim();
          if (id && first && last) {
            return { kind: "ready", referrerId: id, firstName: first, lastName: last };
          }
          if (id && (!first || !last)) {
            return { kind: "incomplete", referrerId: id, firstName: first, lastName: last };
          }
          return { kind: "empty" };
        }
        var legacy = sanitizeReferrerId(trimmed);
        if (legacy) return { kind: "legacy_id", referrerId: legacy };
        return { kind: "empty" };
      } catch (e) {
        return { kind: "empty" };
      }
    }

    function showRecommendIdentityModal(storageKey, prefillFirst, prefillLast) {
      return new Promise(function (resolve) {
        var modal = document.getElementById("recommend-identity-modal");
        var firstEl = document.getElementById("recommend-id-first");
        var lastEl = document.getElementById("recommend-id-last");
        var btnOk = document.getElementById("recommend-id-confirm");
        var btnCancel = document.getElementById("recommend-id-cancel");
        if (!modal || !firstEl || !lastEl || !btnOk || !btnCancel) {
          resolve(null);
          return;
        }
        firstEl.value = prefillFirst || "";
        lastEl.value = prefillLast || "";
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");

        function cleanup() {
          modal.classList.remove("is-open");
          modal.setAttribute("aria-hidden", "true");
          btnOk.onclick = null;
          btnCancel.onclick = null;
        }

        btnCancel.onclick = function () {
          cleanup();
          resolve(null);
        };

        btnOk.onclick = function () {
          var fn = (firstEl.value || "").trim();
          var ln = (lastEl.value || "").trim();
          if (!fn || !ln) {
            showToast("Merci de renseigner votre prénom et votre nom.", true);
            return;
          }
          // Dès qu'un nouveau profil est validé, on force un nouvel ID opaque "rec_*".
          // On n'hérite jamais d'un ancien ID legacy (ex: "marc").
          var rid = generateRecommendationToken();
          if (!rid) {
            showToast("Impossible de créer le lien. Réessayez.", true);
            return;
          }
          try {
            localStorage.setItem(
              storageKey,
              JSON.stringify({
                referrerId: rid,
                firstName: fn,
                lastName: ln,
              })
            );
          } catch (e) {}
          cleanup();
          resolve({ referrerId: rid, firstName: fn, lastName: ln });
        };
      });
    }

    async function ensureReferrerProfileForRecommendationLink(storageKey) {
      // Règle métier: chaque nouvelle action de recommandation repart de zéro.
      // Aucun profil antérieur (ready/legacy/incomplete) ne doit bypasser la saisie.
      // On garde l'écriture storage pour compat/traçabilité locale, mais la lecture
      // ne sert plus à auto-réinjecter ni à sauter la modale.
      return await showRecommendIdentityModal(storageKey, "", "");
    }

    function guessEmoji(card) {
      const name = (card.company_name || "").toLowerCase();
      const slug = (card.slug || "").toLowerCase();
      const str = name + " " + slug;

      if (str.includes("plomb") || str.includes("chauffage")) return "🔧";
      if (str.includes("électric") || str.includes("electric")) return "💡";
      if (str.includes("coiff") || str.includes("hair")) return "💇‍♀️";
      if (str.includes("resto") || str.includes("restaurant")) return "🍽️";
      if (str.includes("pizza")) return "🍕";
      if (str.includes("garage") || str.includes("auto") || str.includes("car")) return "🚗";
      if (str.includes("santé") || str.includes("medical") || str.includes("clinique")) return "🩺";
      if (str.includes("sophro") || str.includes("bien-être") || str.includes("bien etre")) return "🧘";
      if (str.includes("immo") || str.includes("agence") || str.includes("logement")) return "🏡";

      return "🏷️";
    }

    function stripLegacyThemeClasses() {
      const kept = document.body.className
        .split(/\s+/)
        .filter((c) => c && !c.startsWith("theme-"));
      document.body.className = kept.join(" ");
    }

    function applyTheme(themeName, card) {
      const visualTheme = (document.body.getAttribute("data-theme") || "").trim();
      if (visualTheme) {
        stripLegacyThemeClasses();
        return;
      }

      let raw = (themeName || "").toLowerCase().trim();

      stripLegacyThemeClasses();

      if (!raw) {
        document.body.classList.add("theme-apple");
        return;
      }

      let key = raw
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .replace(/–/g, "-")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");

      if (raw.includes("effet") || raw.includes("wow")) {
        if (raw.includes("artisan")) key = "wow-artisan";
        else if (raw.includes("gold")) key = "wow-gold";
        else if (raw.includes("sante") || raw.includes("bien-etre") || raw.includes("bien etre")) key = "wow-health";
        else if (raw.includes("saas") || raw.includes("digital")) key = "wow-saas";
      }

      if (!key) key = "apple";
      document.body.classList.add("theme-" + key);
    }

    function updateQrCode(slug) {
      const img = document.getElementById("qr-image");
      if (!img || !slug) return;
      const url = getPublicCardUrl(slug);
      img.src =
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=" +
        encodeURIComponent(url) +
        "&color=000000&bgcolor=FFFFFF";
    }

    const PROFILE_CONFIG = {
      artisan: {
        mainIcon: (card) => guessEmoji(card),
        badgeLeftIcon: "⭐",
        badgeLeftText: "Entreprise recommandée",
        badgeRightIcon: "📍",
        badgeRightText: "Service de proximité",
        heroSubtitle: "Contact, avis Google et demandes de devis en un seul lien.",
        leftBlockTitle: "Avis & contacts simplifiés",
        quoteSectionLabel: "Demande de devis",
        quoteButtonLabel: "Envoyer ma demande de devis",
        quoteToast: "Demande de devis envoyée !",
      },
      digital: {
        mainIcon: "💻",
        badgeLeftIcon: "💡",
        badgeLeftText: "Profil digital",
        badgeRightIcon: "🛒",
        badgeRightText: "Produit en ligne",
        heroSubtitle: "Présentation, contact et accès direct à vos liens digitaux en un seul endroit.",
        leftBlockTitle: "Contact & actions rapides",
        quoteSectionLabel: "Demande de contact / démo",
        quoteButtonLabel: "Envoyer ma demande de démo",
        quoteToast: "Demande de contact envoyée !",
      },
      bien_etre: {
        mainIcon: "🧘",
        badgeLeftIcon: "🌿",
        badgeLeftText: "Praticien bien-être",
        badgeRightIcon: "📅",
        badgeRightText: "Sur rendez-vous",
        heroSubtitle: "Retours clients, prises de rendez-vous et informations en un seul lien.",
        leftBlockTitle: "Avis & ressentis de vos clients",
        quoteSectionLabel: "Demande de rendez-vous",
        quoteButtonLabel: "Envoyer ma demande de rendez-vous",
        quoteToast: "Demande de rendez-vous envoyée !",
      },
      medical: {
        mainIcon: "🩺",
        badgeLeftIcon: "🏥",
        badgeLeftText: "Professionnel de santé",
        badgeRightIcon: "📅",
        badgeRightText: "Sur rendez-vous",
        heroSubtitle: "Coordonnées, informations et prises de rendez-vous en un seul lien.",
        leftBlockTitle: "Avis & retours patients",
        quoteSectionLabel: "Demande de rendez-vous",
        quoteButtonLabel: "Envoyer ma demande de rendez-vous",
        quoteToast: "Demande de rendez-vous envoyée !",
      },
      immo: {
        mainIcon: "🏡",
        badgeLeftIcon: "🏡",
        badgeLeftText: "Agence / Conseiller immo",
        badgeRightIcon: "📍",
        badgeRightText: "Biens à proximité",
        heroSubtitle: "Contact, avis et demandes de visite ou d’estimation en un seul lien.",
        leftBlockTitle: "Avis & contacts simplifiés",
        quoteSectionLabel: "Demande de visite / estimation",
        quoteButtonLabel: "Envoyer ma demande",
        quoteToast: "Demande envoyée !",
      },
      resto: {
        mainIcon: "🍽️",
        badgeLeftIcon: "⭐",
        badgeLeftText: "Restaurant recommandé",
        badgeRightIcon: "📅",
        badgeRightText: "Réservation conseillée",
        heroSubtitle: "Menu, avis et réservations en un seul lien.",
        leftBlockTitle: "Avis & réservations rapides",
        quoteSectionLabel: "Demande de réservation",
        quoteButtonLabel: "Envoyer ma demande de réservation",
        quoteToast: "Demande de réservation envoyée !",
      },
    };

    let CURRENT_PROFILE_CONFIG = PROFILE_CONFIG.artisan;

    /** Garde-fou : un seul envoi visit_from_recommendation par chargement de page. */
    let visitFromRecommendationEventDone = false;

    function revealCardShell() {
      requestAnimationFrame(function () {
        document.body.classList.remove("is-loading");
        document.body.classList.add("is-ready");
        var loadLayer = document.getElementById("premium-load-layer");
        if (loadLayer) {
          loadLayer.setAttribute("aria-busy", "false");
          loadLayer.setAttribute("aria-hidden", "true");
        }
      });
    }

    function resolvePublicCardUiLegacy(card) {
      try {
        var p = new URLSearchParams(window.location.search || "");
        if ((p.get("lang") || "").trim().toLowerCase() === "es") return true;
      } catch (e) {}
      if (card && (card.region || "").toString().trim().toLowerCase() === "latam") return true;
      return false;
    }

    function applyPublicCardUiMode(card) {
      var legacy = resolvePublicCardUiLegacy(card);
      document.body.classList.toggle("public-card--legacy", legacy);
      document.body.classList.toggle("public-card--compact", !legacy);
    }

    /** Recalcule thème + mode compact + slots DOM (fix affichage initial mobile). */
    function refreshLayout(card) {
      if (card) {
        applyVisualThemeFromCard(card);
        applyPublicCardUiMode(card);
        initWellnessMinimalQuoteModal();
      } else {
        applyPublicCardUiMode(null);
      }
      syncCompactContactSlots();
      void document.documentElement.offsetHeight;
      try {
        window.dispatchEvent(new Event("resize"));
      } catch (e) {
        var ev = document.createEvent("Event");
        ev.initEvent("resize", true, true);
        window.dispatchEvent(ev);
      }
    }

    function scheduleLayoutRefresh(card) {
      refreshLayout(card);
      requestAnimationFrame(function () {
        refreshLayout(card);
      });
    }

    function syncCompactContactSlots() {
      var compact = document.body.classList.contains("public-card--compact");
      var heroTel = document.getElementById("slot-call-wa-hero");
      var heroAdd = document.getElementById("slot-add-contact-hero");
      var slotCall = document.getElementById("slot-call-legacy");
      var slotWa = document.getElementById("slot-wa-legacy");
      var slotAdd = document.getElementById("slot-add-legacy");
      var call = document.getElementById("btn-call");
      var wa = document.getElementById("btn-whatsapp");
      var add = document.getElementById("btn-add-contact");
      if (!call || !wa || !add) return;
      if (compact && heroTel && heroAdd) {
        heroTel.appendChild(call);
        heroTel.appendChild(wa);
        heroAdd.appendChild(add);
      } else if (!compact && slotCall && slotWa && slotAdd) {
        slotCall.appendChild(call);
        slotWa.appendChild(wa);
        slotAdd.appendChild(add);
      }
    }

    function setupHeroSocialLinks(card) {
      var wrap = document.getElementById("hero-compact-social");
      var elFb = document.getElementById("hero-link-facebook");
      var elIg = document.getElementById("hero-link-instagram");
      if (!elFb || !elIg) return;
      function normUrl(u) {
        var s = (u || "").toString().trim();
        if (!s) return "";
        return /^https?:\/\//i.test(s) ? s : "https://" + s;
      }
      var fb = (card && card.facebook) ? normUrl(card.facebook) : "";
      var ig = (card && card.instagram) ? normUrl(card.instagram) : "";
      var show = false;
      if (fb) {
        elFb.href = fb;
        elFb.removeAttribute("hidden");
        show = true;
      } else {
        elFb.setAttribute("hidden", "");
      }
      if (ig) {
        elIg.href = ig;
        elIg.removeAttribute("hidden");
        show = true;
      } else {
        elIg.setAttribute("hidden", "");
      }
      if (wrap) {
        var compact = document.body.classList.contains("public-card--compact");
        wrap.hidden = !compact || !show;
      }
    }

    function syncCompactActionTriggers(showRecommendBlock) {
      if (!document.body.classList.contains("public-card--compact")) return;
      var ownerShare = document.body.classList.contains("owner-share-tools");
      var shareT = document.getElementById("acc-trigger-share");
      var recT = document.getElementById("acc-trigger-recommend");
      var payT = document.getElementById("acc-trigger-pay");
      var payBtn = document.getElementById("btn-pay");
      var btnRec = document.getElementById("btn-cta-recommander");
      var btnShareD = document.getElementById("btn-discrete-partager");
      var btnPayD = document.getElementById("btn-discrete-paiement");
      if (shareT) shareT.hidden = !ownerShare;
      if (btnShareD) btnShareD.hidden = !ownerShare;
      if (recT) recT.hidden = !showRecommendBlock;
      if (btnRec) btnRec.hidden = !showRecommendBlock;
      if (payT && payBtn) {
        var payOff = !!payBtn.disabled;
        payT.hidden = payOff;
        if (btnPayD) btnPayD.hidden = payOff;
      }
    }

    function initPublicCardAccordion() {
      if (!document.body.classList.contains("public-card--compact")) return;
      var triggers = document.querySelectorAll("[data-acc-trigger]");
      var panels = document.querySelectorAll(".acc-panel[data-acc-panel]");
      triggers.forEach(function (t) {
        if (t.getAttribute("data-acc-bound") === "1") return;
        t.setAttribute("data-acc-bound", "1");
        t.addEventListener("click", function (e) {
          e.preventDefault();
          var key = t.getAttribute("data-acc-trigger");
          if (!key) return;
          var panel = document.querySelector('.acc-panel[data-acc-panel="' + key + '"]');
          var nowOpen = panel && panel.classList.contains("is-open");
          panels.forEach(function (p) {
            p.classList.remove("is-open");
          });
          triggers.forEach(function (x) {
            x.setAttribute("aria-expanded", "false");
          });
          if (!nowOpen && panel) {
            panel.classList.add("is-open");
            t.setAttribute("aria-expanded", "true");
          }
        });
      });
    }

    function openCompactAccordionPanel(key) {
      if (!document.body.classList.contains("public-card--compact") || !key) return;
      var panel = document.querySelector('.acc-panel[data-acc-panel="' + key + '"]');
      var tr = document.querySelector('[data-acc-trigger="' + key + '"]');
      var panels = document.querySelectorAll(".acc-panel[data-acc-panel]");
      var triggers = document.querySelectorAll("[data-acc-trigger]");
      panels.forEach(function (p) {
        p.classList.remove("is-open");
      });
      triggers.forEach(function (x) {
        x.setAttribute("aria-expanded", "false");
      });
      if (panel) panel.classList.add("is-open");
      if (tr) tr.setAttribute("aria-expanded", "true");
    }

    async function loadCard() {
      applyPublicCardUiMode(null);
      const slug = getSlugFromPath();
      if (!slug) {
        showToast("Slug introuvable dans l’URL", true);
        revealCardShell();
        return;
      }

      syncInternalViewFromUrl(slug);
      refreshIsInternalView(slug);

      const isDemoCard = isDemoSlug(slug);
      document.body.classList.toggle("client-card-mode", !isDemoCard);
      applyClientMidsectionVisibility(isDemoCard);
      document.querySelectorAll(".demo-marketing").forEach(function (el) {
        el.classList.toggle("demo-marketing--on", isDemoCard);
        el.setAttribute("aria-hidden", isDemoCard ? "false" : "true");
      });

      if (isDemoCard) {
        document.body.classList.add("owner-share-tools");
      } else {
        document.body.classList.remove("owner-share-tools");
      }

      const referrerIdFromUrl = getRecommendationReferrerIdFromUrl();
      syncRecommendTrustBanner(null);

      try {
        var apiUrl = "/api/public/cards/" + encodeURIComponent(slug);
        var ownerKeyParam = getOwnerShareKeyFromUrl();
        var queryParts = [];
        if (ownerKeyParam) queryParts.push("o=" + encodeURIComponent(ownerKeyParam));
        if (referrerIdFromUrl) queryParts.push("r=" + encodeURIComponent(referrerIdFromUrl));
        if (queryParts.length) {
          apiUrl += "?" + queryParts.join("&");
        }
        const res = await fetch(apiUrl);
        if (!res.ok) {
          hideRecommendTrustBanner();
          let errorDetail = "Carte introuvable";
          try {
            const errorData = await res.json();
            if (errorData && errorData.detail) errorDetail = errorData.detail;
          } catch (e) {}
          const inactiveBox = document.getElementById("inactive-card-message");
          if (res.status === 403 && inactiveBox) {
            inactiveBox.textContent = errorDetail;
            inactiveBox.style.display = "block";
            const shell = document.querySelector(".phone-shell");
            if (shell) shell.style.display = "none";
          } else {
            showToast(errorDetail, true);
            revealCardShell();
          }
          return;
        }

        const card = await res.json();
        // Slug canonique API (lookup devis / recommendation_events) — évite écart casse/path vs DB.
        const analyticsSlug =
          (card.slug != null && card.slug !== undefined && String(card.slug).trim())
            ? String(card.slug).trim()
            : slug;

        var showOwnerShareTools = !!isDemoCard || card.owner_mode === true;
        document.body.classList.toggle("owner-share-tools", showOwnerShareTools);
        var btnShareMainEarly = document.getElementById("btn-share-card-main");
        if (btnShareMainEarly && showOwnerShareTools) {
          btnShareMainEarly.textContent = "📲 Envoyer ma carte";
        }
        const cardId = card.id;
        const recommendationVisitorId = referrerIdFromUrl
          ? getOrCreateRecommendationVisitorId()
          : null;

        syncRecommendTrustBanner(
          card.recommend_arrival_attribution != null
            ? card.recommend_arrival_attribution
            : null
        );

        trackCardVisit(analyticsSlug);

        if (shouldTrackAnalytics() && referrerIdFromUrl) {
          trackRecommendationEvent(
            analyticsSlug,
            "recommend_visit",
            referrerIdFromUrl,
            recommendationVisitorId
          );
        }

        if (
          shouldTrackAnalytics() &&
          !visitFromRecommendationEventDone &&
          isRecommendSourceParam()
        ) {
          visitFromRecommendationEventDone = true;
          trackCardEvent(analyticsSlug, "visit_from_recommendation");
        }

        applyVisualThemeFromCard(card);
        initWellnessMinimalQuoteModal();

        const rawProfile = (card.profile || "").toLowerCase();
        const profileKey = PROFILE_CONFIG[rawProfile] ? rawProfile : "artisan";
        CURRENT_PROFILE_CONFIG = PROFILE_CONFIG[profileKey];

        /* FR /c/{slug} : habillage = data-theme (visual_theme SSR + API). Pas de classes theme-* legacy. */
        if (/^\/c\/[^/]+/i.test(window.location.pathname || "")) {
          stripLegacyThemeClasses();
        } else {
          applyTheme(card.theme, card);
        }

        const companyName = (card.company_name || "Votre entreprise").toString().trim();

        const first = (card.first_name || card.prenom || card.firstname || "").toString().trim();
        const last = (card.last_name || card.nom || card.lastname || "").toString().trim();
        const fullName = `${first} ${last}`.trim();

        const displayNameRaw = (card.display_name != null && card.display_name !== undefined
          ? String(card.display_name)
          : "").trim();
        const businessNameRaw = (card.business_name != null && card.business_name !== undefined
          ? String(card.business_name)
          : "").trim();

        // Persisté uniquement : display_name sinon company_name (first/last ne sont pas en base)
        const primaryName = displayNameRaw || companyName;

        const personEl = document.getElementById("person-name");
        const companyEl = document.getElementById("company-name");

        if (personEl) personEl.textContent = primaryName;

        if (isWellnessVisualTheme()) {
          const recoTitleEl = document.getElementById("wellness-reco-title-text");
          if (recoTitleEl) {
            const firstName = (primaryName || "").trim().split(/\s+/)[0];
            recoTitleEl.textContent =
              firstName && !/^prénom$/i.test(firstName)
                ? "Recommander " + firstName
                : "Recommander ce professionnel";
          }
        }

        if (companyEl) {
          if (
            businessNameRaw &&
            businessNameRaw.toLowerCase() !== primaryName.toLowerCase()
          ) {
            companyEl.textContent = businessNameRaw;
            companyEl.style.display = "";
          } else {
            companyEl.style.display = "none";
          }
        }

        applyPublicShellCopy(isDemoCard, companyName, primaryName);
        updateFrenchCardSeo(card, analyticsSlug, primaryName);
        updateFrenchCardOgImage(card, analyticsSlug);

        function runAvatarBlock(card) {
          const avatarImg = document.getElementById("hero-avatar-img");
          const avatarFallback = document.getElementById("hero-avatar-fallback");
          const avatarPlaceholder = document.getElementById("hero-avatar-placeholder");
          if (!avatarImg || !avatarFallback || !avatarPlaceholder) return;

          const avatarUrl = (card.avatar_url || "").toString().trim();

          const getInitials = () => {
            const dn = (card.display_name || "").toString().trim();
            if (dn) {
              const parts = dn.split(/\s+/).filter(Boolean);
              if (parts.length >= 2) {
                const s = ((parts[0][0] || "") + (parts[1][0] || "")).toUpperCase();
                if (s) return s;
              }
              if (parts.length === 1 && parts[0].length) {
                return parts[0].slice(0, 2).toUpperCase();
              }
            }
            const first = (card.first_name || card.prenom || card.firstname || "").toString().trim();
            const last = (card.last_name || card.nom || card.lastname || "").toString().trim();
            const company = (card.company_name || "").toString().trim();
            if (first || last) {
              const s = ((first[0] || "") + (last[0] || "")).toUpperCase();
              return s || (first + last).slice(0, 2).toUpperCase();
            }
            if (company) return company.slice(0, 2).toUpperCase();
            return "MC";
          };

          let placeholderHideTimer = null;
          const clearPlaceholderHideTimer = () => {
            if (placeholderHideTimer != null) {
              clearTimeout(placeholderHideTimer);
              placeholderHideTimer = null;
            }
          };

          const showInitialsOnly = () => {
            clearPlaceholderHideTimer();
            avatarPlaceholder.classList.add("is-hidden");
            avatarImg.classList.remove("is-loaded");
            avatarImg.removeAttribute("src");
            avatarImg.onload = null;
            avatarImg.onerror = null;
            avatarFallback.textContent = getInitials();
            avatarFallback.style.display = "flex";
            avatarFallback.style.zIndex = "1";
          };

          if (!avatarUrl) {
            showInitialsOnly();
            return;
          }

          avatarImg.onload = null;
          avatarImg.onerror = null;
          clearPlaceholderHideTimer();
          avatarImg.classList.remove("is-loaded");
          avatarFallback.style.display = "none";
          avatarFallback.textContent = "";
          avatarPlaceholder.classList.remove("is-hidden");
          avatarImg.removeAttribute("src");

          avatarImg.onload = () => {
            requestAnimationFrame(function () {
              requestAnimationFrame(function () {
                clearPlaceholderHideTimer();
                avatarImg.classList.add("is-loaded");

                placeholderHideTimer = window.setTimeout(function () {
                  avatarPlaceholder.classList.add("is-hidden");
                  placeholderHideTimer = null;
                }, 220);
              });
            });
          };

          avatarImg.onerror = () => {
            clearPlaceholderHideTimer();
            avatarImg.classList.remove("is-loaded");
            avatarImg.removeAttribute("src");
            showInitialsOnly();
          };

          avatarImg.src = avatarUrl;
        }

        runAvatarBlock(card);

        const compactUi = !resolvePublicCardUiLegacy(card);

        const DEFAULT_HERO_TITLE = isDemoCard
          ? "Contact, avis et demande en 1 clic"
          : "Coordonnées, avis et demandes en ligne";
        const DEFAULT_REASSURANCE = isDemoCard
          ? "⭐ Plus d’avis Google. Plus de clients."
          : "⭐ Avis clients, messages et demandes simplifiés.";
        const DEFAULT_SOCIAL_PROOF = isDemoCard
          ? "Déjà utilisé par des artisans, thérapeutes et indépendants"
          : "Une présentation claire pour vos clients et prospects.";

        const rawJobTitle = (card.job_title || "").toString().trim();
        const rawHeroTitle = (card.hero_title || "").toString().trim();

        const jobTitleEl = document.getElementById("hero-job-title");
        if (jobTitleEl) {
          if (rawJobTitle) {
            jobTitleEl.textContent = rawJobTitle;
            jobTitleEl.style.display = "";
            jobTitleEl.setAttribute("aria-hidden", "false");
          } else {
            jobTitleEl.textContent = "";
            jobTitleEl.style.display = "none";
            jobTitleEl.setAttribute("aria-hidden", "true");
          }
        }

        const cityRaw = (
          (card.city != null && String(card.city).trim()) ||
          (card.service_city != null && String(card.service_city).trim()) ||
          ""
        )
          .toString()
          .trim();
        const cityEl = document.getElementById("hero-city");
        if (cityEl) {
          if (cityRaw && isPortraitHeroTheme()) {
            cityEl.textContent = cityRaw;
            cityEl.style.display = "";
            cityEl.setAttribute("aria-hidden", "false");
          } else {
            cityEl.textContent = "";
            cityEl.style.display = "none";
            cityEl.setAttribute("aria-hidden", "true");
          }
        }

        const heroTaglineEl = document.getElementById("hero-professional-tagline");
        if (heroTaglineEl) {
          if (rawHeroTitle) {
            heroTaglineEl.textContent = rawHeroTitle;
            heroTaglineEl.style.display = "";
          } else if (!compactUi || isDemoCard) {
            heroTaglineEl.textContent = DEFAULT_HERO_TITLE;
            heroTaglineEl.style.display = "";
          } else {
            heroTaglineEl.textContent = "";
            heroTaglineEl.style.display = "none";
          }
        }

        const recommendShareCount = Math.max(
          0,
          Math.floor(Number(card.recommendation_share_count) || 0)
        );
        const heroRecommendCountEl = document.getElementById("hero-recommend-count");
        const heroRecommendConversionEl = document.getElementById("hero-recommend-conversion");
        if (heroRecommendCountEl) {
          if (recommendShareCount >= 1) {
            heroRecommendCountEl.textContent =
              recommendShareCount === 1
                ? "Une recommandation personnelle a déjà été partagée 👍"
                : recommendShareCount +
                  " recommandations personnelles ont déjà été partagées 👍";
            heroRecommendCountEl.hidden = false;
            heroRecommendCountEl.setAttribute("aria-hidden", "false");
            if (heroRecommendConversionEl) {
              heroRecommendConversionEl.classList.add("is-visible");
              heroRecommendConversionEl.setAttribute("aria-hidden", "false");
            }
          } else {
            heroRecommendCountEl.textContent = "";
            heroRecommendCountEl.hidden = true;
            heroRecommendCountEl.setAttribute("aria-hidden", "true");
            if (heroRecommendConversionEl) {
              heroRecommendConversionEl.classList.remove("is-visible");
              heroRecommendConversionEl.setAttribute("aria-hidden", "true");
            }
          }
        }

        const reassuranceEl = document.getElementById("hero-reassurance");
        const socialProofEl = document.getElementById("hero-social-proof");
        const rawHeroText = (card.hero_text || "").toString().trim();
        if (reassuranceEl && socialProofEl) {
          if (rawHeroText) {
            reassuranceEl.textContent = rawHeroText;
            reassuranceEl.style.display = "";
            socialProofEl.textContent = "";
            socialProofEl.style.display = "none";
          } else if (!compactUi || isDemoCard) {
            reassuranceEl.textContent = DEFAULT_REASSURANCE;
            reassuranceEl.style.display = "";
            socialProofEl.textContent = DEFAULT_SOCIAL_PROOF;
            socialProofEl.style.display = "";
          } else {
            reassuranceEl.textContent = "";
            reassuranceEl.style.display = "none";
            socialProofEl.textContent = "";
            socialProofEl.style.display = "none";
          }
        }

        const subtitleEl = document.getElementById("hero-subtitle");
        const rawHeroCta = (card.hero_cta_text || "").toString().trim();
        if (subtitleEl) {
          if (rawHeroCta) {
            subtitleEl.textContent = rawHeroCta;
            subtitleEl.style.display = "";
          } else if (!compactUi || isDemoCard) {
            subtitleEl.textContent =
              CURRENT_PROFILE_CONFIG.heroSubtitle ||
              (isDemoCard
                ? "Carte pro intelligente Maavnica."
                : "Contact, avis et demandes en ligne.");
            subtitleEl.style.display = "";
          } else {
            subtitleEl.textContent = "";
            subtitleEl.style.display = "none";
          }
        }

        const badgeLeftIcon = document.getElementById("hero-badge-left-icon");
        const badgeLeftText = document.getElementById("hero-badge-left-text");
        const badgeRightIcon = document.getElementById("hero-badge-right-icon");
        const badgeRightText = document.getElementById("hero-badge-right-text");

        if (badgeLeftIcon && badgeLeftText && badgeRightIcon && badgeRightText) {
          badgeLeftIcon.textContent = CURRENT_PROFILE_CONFIG.badgeLeftIcon || "⭐";
          badgeLeftText.textContent = CURRENT_PROFILE_CONFIG.badgeLeftText || badgeLeftText.textContent;
          badgeRightIcon.textContent = CURRENT_PROFILE_CONFIG.badgeRightIcon || "📍";
          badgeRightText.textContent = CURRENT_PROFILE_CONFIG.badgeRightText || badgeRightText.textContent;
        }

        const mainBlockTitle = document.getElementById("block-title-main");
        if (mainBlockTitle) {
          if (!isDemoCard) {
            mainBlockTitle.textContent = "Contact & avis";
          } else if (CURRENT_PROFILE_CONFIG.leftBlockTitle) {
            mainBlockTitle.textContent = CURRENT_PROFILE_CONFIG.leftBlockTitle;
          }
        }

        const quoteSectionLabel = document.getElementById("quote-section-label");
        const rawFormTitle = (card.form_title || "").toString().trim();
        if (quoteSectionLabel) {
          if (rawFormTitle) {
            quoteSectionLabel.textContent = rawFormTitle;
          } else if (!isDemoCard) {
            quoteSectionLabel.textContent = "Demande de contact";
          } else if (CURRENT_PROFILE_CONFIG.quoteSectionLabel) {
            quoteSectionLabel.textContent = CURRENT_PROFILE_CONFIG.quoteSectionLabel;
          }
        }

        const btnPrimaryContact = document.getElementById("btn-primary-demande-contact");
        const wellnessCtaLabel = document.getElementById("wellness-cta-label");
        if (
          btnPrimaryContact &&
          isWellnessVisualTheme()
        ) {
          var wellnessCta = rawFormTitle;
          if (!wellnessCta) {
            if (profileKey === "bien_etre" || profileKey === "medical") {
              wellnessCta = "Prendre rendez-vous";
            } else {
              wellnessCta = "Demande de contact";
            }
          }
          if (wellnessCtaLabel) {
            wellnessCtaLabel.textContent = wellnessCta.toUpperCase();
          } else {
            btnPrimaryContact.textContent = wellnessCta.toUpperCase();
          }
        }

        const quoteBtn = document.getElementById("btn-send-quote");
        if (quoteBtn && CURRENT_PROFILE_CONFIG.quoteButtonLabel) {
          quoteBtn.textContent = "📝 " + CURRENT_PROFILE_CONFIG.quoteButtonLabel;
        }

        const availabilityNote = document.getElementById("hero-availability-note");
        if (availabilityNote) availabilityNote.textContent = "";

        const emailLine = document.getElementById("hero-email-line");
        const emailEl = document.getElementById("hero-email");
        const siteLine = document.getElementById("hero-site-line");
        const siteEl = document.getElementById("hero-site");

        const email = card.email_pro || card.email || null;
        const website = card.site_web || card.website || null;

        if (!email && !website) {
          emailEl.textContent = "Email non renseigné";
          emailLine.style.opacity = "0.7";
          siteEl.textContent = "Site ou lien principal";
          siteLine.style.opacity = "0.7";
        } else {
          emailEl.textContent = email || "Email non renseigné";
          emailLine.style.opacity = email ? "1" : "0.7";
          siteEl.textContent = website || "Site ou lien principal";
          siteLine.style.opacity = website ? "1" : "0.7";
        }

        const btnGoogle = document.getElementById("btn-google-review");
        if (btnGoogle) {
          if (card.google_review_link) {
            btnGoogle.disabled = false;
            btnGoogle.onclick = () => {
              trackCardEvent(analyticsSlug, "google_review_click");
              window.open(card.google_review_link, "_blank", "noopener");
            };
          } else {
            btnGoogle.disabled = true;
            btnGoogle.onclick = null;
          }
        }

        (function renderHeroGoogleRatingBadges() {
          const rating =
            card.google_rating != null && card.google_rating !== ""
              ? parseFloat(card.google_rating)
              : null;
          const count =
            card.google_review_count != null && card.google_review_count !== ""
              ? parseInt(card.google_review_count, 10)
              : null;
          const hasRating = typeof rating === "number" && !isNaN(rating);
          const hasCount = typeof count === "number" && !isNaN(count) && count >= 0;
          const reviewLink = (card.google_review_link || "").toString().trim();
          const isWellnessTheme =
            isWellnessVisualTheme();
          ["hero-google-badge", "hero-google-badge-compact"].forEach(function (id) {
            const googleBadgeEl = document.getElementById(id);
            if (!googleBadgeEl) return;
            if (hasRating && hasCount) {
              const ratingStr = rating.toFixed(1).replace(".", ",");
              googleBadgeEl.textContent = "";
              googleBadgeEl.classList.toggle(
                "wellness-google-rating-card",
                isWellnessTheme
              );
              if (isWellnessTheme) {
                const inner = document.createElement("div");
                inner.className = "wellness-google-inner";

                const left = document.createElement("div");
                left.className = "wellness-google-left";

                const starEl = document.createElement("span");
                starEl.className = "wellness-google-star-icon";
                starEl.textContent = "★";

                const scoreEl = document.createElement("span");
                scoreEl.className = "wellness-google-score";
                scoreEl.textContent = ratingStr;

                const labelEl = document.createElement("span");
                labelEl.className = "wellness-google-label";
                labelEl.textContent = "sur Google";

                left.appendChild(starEl);
                left.appendChild(scoreEl);
                left.appendChild(labelEl);

                const countEl = document.createElement("span");
                countEl.className = "wellness-google-count";
                countEl.textContent = count + " avis";

                const avatarsEl = document.createElement("div");
                avatarsEl.className = "wellness-google-avatars";
                avatarsEl.setAttribute("aria-hidden", "true");
                for (var avi = 0; avi < 3; avi++) {
                  var av = document.createElement("span");
                  av.className = "wellness-google-avatar";
                  avatarsEl.appendChild(av);
                }

                inner.appendChild(left);
                inner.appendChild(countEl);
                inner.appendChild(avatarsEl);

                if (reviewLink) {
                  const a = document.createElement("a");
                  a.href = reviewLink;
                  a.target = "_blank";
                  a.rel = "noopener";
                  a.appendChild(inner);
                  a.addEventListener("click", function () {
                    trackCardEvent(analyticsSlug, "google_review_click");
                  });
                  googleBadgeEl.appendChild(a);
                } else {
                  googleBadgeEl.appendChild(inner);
                }
              } else if (reviewLink) {
                const text = "⭐ " + ratingStr + " sur Google • " + count + " avis";
                const a = document.createElement("a");
                a.href = reviewLink;
                a.target = "_blank";
                a.rel = "noopener";
                a.textContent = text;
                a.addEventListener("click", function () {
                  trackCardEvent(analyticsSlug, "google_review_click");
                });
                googleBadgeEl.appendChild(a);
              } else {
                googleBadgeEl.textContent =
                  "⭐ " + ratingStr + " sur Google • " + count + " avis";
              }
              googleBadgeEl.style.display = "flex";
            } else {
              googleBadgeEl.textContent = "";
              googleBadgeEl.classList.remove("wellness-google-rating-card");
              googleBadgeEl.style.display = "none";
            }
          });
        })();

        const cardPublicUrl = getPublicCardUrl(analyticsSlug);
        const cityShare = (
          (card.city != null && String(card.city).trim()) ||
          (card.service_city != null && String(card.service_city).trim()) ||
          ""
        )
          .toString()
          .trim();

        function trimShareText(s) {
          return (s || "").toString().replace(/\s+/g, " ").trim();
        }

        /** Libellé humain court : nom / métier / ville / société (fallbacks propres). */
        function getProViralLabelForShare() {
          const placeholderName = /^prénom\s*nom$/i.test((primaryName || "").trim());
          const name =
            primaryName &&
            !placeholderName &&
            primaryName !== "Votre entreprise"
              ? primaryName.trim()
              : "";
          const job = (rawJobTitle || "").trim();
          const city = cityShare;
          const biz = (businessNameRaw || "").trim();
          const co =
            companyName && companyName !== "Votre entreprise"
              ? companyName.trim()
              : "";
          if (name && job && city) return name + ", " + job + " à " + city;
          if (name && job) return name + ", " + job;
          if (name && city) return name + " à " + city;
          if (name) return name;
          if (biz) return biz;
          if (co) return co;
          return "";
        }

        /** Texte partage natif (sans URL — passée à part via sharePayload.url). */
        function getOwnerShareTextNative() {
          const who = getProViralLabelForShare();
          if (isDemoCard) {
            if (who) {
              return trimShareText(
                "Bonjour 👋 Je te partage ma carte Maavnica — " +
                  who +
                  ". Tu peux me contacter ou laisser un avis si tu veux."
              );
            }
            return trimShareText(
              "Bonjour 👋 Je te partage ma carte Maavnica pour qu’on reste en contact facilement."
            );
          }
          if (who) {
            return trimShareText(
              "Bonjour 👋 Voici ma carte — " +
                who +
                ". N’hésite pas si tu as besoin de moi."
            );
          }
          return trimShareText(
            "Bonjour 👋 Voici ma carte de contact : tu peux me joindre ou me laisser un message."
          );
        }

        /** SMS / e-mail : une seule URL en fin de message. */
        function getOwnerShareTextWithLink() {
          return trimShareText(getOwnerShareTextNative() + "\n\n" + cardPublicUrl);
        }

        function getOwnerShareTitle() {
          if (isDemoCard) return "Ma carte Maavnica";
          const who = getProViralLabelForShare();
          if (who) {
            var short = who.split(",")[0].trim();
            if (short.length > 42) short = short.slice(0, 39).trim() + "…";
            return "Ma carte — " + short;
          }
          return "Ma carte de contact";
        }

        function getOwnerEmailSubject() {
          return getOwnerShareTitle();
        }

        function getRecommendShareTextNative() {
          const who = getProViralLabelForShare();
          if (who) {
            return trimShareText(
              "Je te recommande " + who + " 👌 Petite carte simple pour le contacter."
            );
          }
          return trimShareText(
            "Je te recommande ce professionnel 👌 Voici sa carte pour le contacter facilement."
          );
        }

        function getRecommendShareTextWithLink(recommendShareUrl) {
          return trimShareText(
            getRecommendShareTextNative() + "\n\n" + recommendShareUrl
          );
        }

        function getRecommendShareTitle() {
          const who = getProViralLabelForShare();
          if (who) {
            var head = who.split(",")[0].trim();
            if (head.length > 36) head = head.slice(0, 33).trim() + "…";
            return "Reco — " + head;
          }
          return "Une recommandation pour toi";
        }

        function getRecommendEmailSubject() {
          const who = getProViralLabelForShare();
          if (who) {
            var head = who.split(",")[0].trim();
            if (head.length > 48) head = head.slice(0, 45).trim() + "…";
            return "Je te recommande " + head;
          }
          return "Je te recommande ce professionnel";
        }

        const btnWhats = document.getElementById("btn-whatsapp");
        if (btnWhats) {
          const waNumber = card.whatsapp || card.phone;
          if (waNumber) {
            btnWhats.disabled = false;
            btnWhats.onclick = () => {
              trackCardEvent(analyticsSlug, "whatsapp_click");
              if (referrerIdFromUrl) {
                trackRecommendationEvent(
                  analyticsSlug,
                  "recommend_contact",
                  referrerIdFromUrl,
                  recommendationVisitorId
                );
              }
              const base = "https://wa.me/";
              const whoWa = getProViralLabelForShare();
              const msg = encodeURIComponent(
                isDemoCard
                  ? whoWa
                    ? trimShareText(
                        "Bonjour, je vous écris en découvrant votre carte Maavnica (" +
                          whoWa +
                          ")."
                      )
                    : "Bonjour, je vous écris en découvrant votre carte Maavnica."
                  : whoWa
                    ? trimShareText(
                        "Bonjour, je vous contacte après avoir vu votre carte (" +
                          whoWa +
                          ")."
                      )
                    : "Bonjour, je vous contacte depuis votre carte en ligne."
              );
              const digits = waNumber.toString().replace(/[^\d]/g, "");
              window.open(base + digits + "?text=" + msg, "_blank");
            };
          } else {
            btnWhats.disabled = true;
            btnWhats.onclick = null;
          }
        }

        const btnCall = document.getElementById("btn-call");
        if (btnCall) {
          if (card.phone) {
            btnCall.disabled = false;
            btnCall.onclick = () => {
              trackCardEvent(analyticsSlug, "phone_click");
              if (referrerIdFromUrl) {
                trackRecommendationEvent(
                  analyticsSlug,
                  "recommend_contact",
                  referrerIdFromUrl,
                  recommendationVisitorId
                );
              }
              window.location.href = "tel:" + card.phone;
            };
          } else {
            btnCall.disabled = true;
            btnCall.onclick = null;
          }
        }

        const btnPay = document.getElementById("btn-pay");
        if (btnPay) {
          if (card.payment_link) {
            btnPay.disabled = false;
            btnPay.onclick = () => window.open(card.payment_link, "_blank", "noopener");
          } else {
            btnPay.disabled = true;
            btnPay.onclick = null;
          }
        }

        const btnAddContact = document.getElementById("btn-add-contact");
        if (btnAddContact) {
          btnAddContact.href = "/api/public/cards/" + encodeURIComponent(analyticsSlug) + "/vcard";
        }

        const btnFeedback = document.getElementById("btn-send-feedback");
        if (btnFeedback) {
          let feedbackValue = null;
          const pillYes = document.getElementById("pill-yes");
          const pillNo = document.getElementById("pill-no");
          const pillRow = pillYes ? pillYes.closest(".pill-row") : null;
          const helperTextEl = document.getElementById("feedback-helper-text");
          const btnGoogleReview = document.getElementById("btn-google-review");
          const commentEl = document.getElementById("feedback-comment");

          function selectFeedback(value) {
            feedbackValue = value;
            const hasSelection = !!value;
            if (pillYes && pillNo) {
              pillYes.classList.toggle("selected-yes", value === "yes");
              pillNo.classList.toggle("selected-no", value === "no");
            }

            if (pillRow) pillRow.classList.toggle("feedback-has-selection", hasSelection);
            if (commentEl) commentEl.classList.toggle("feedback-comment-visible", hasSelection);
            if (helperTextEl)
              helperTextEl.classList.toggle("feedback-helper-visible", hasSelection);

            if (!value && helperTextEl) {
              helperTextEl.textContent =
                "Choisissez une option ci-dessus pour nous laisser un retour rapide.";
            }
          }

          if (pillYes) {
            pillYes.onclick = () => {
              openCompactAccordionPanel("feedback");
              selectFeedback("yes");
              const googleReviewUrl = (card.google_review_link || "").toString().trim();
              if (helperTextEl) {
                helperTextEl.textContent =
                  "Merci 🙌 Votre avis aide beaucoup ce professionnel.";
              }
              if (commentEl) {
                commentEl.placeholder = "Un mot sur votre expérience (optionnel)";
              }
              if (btnFeedback) {
                btnFeedback.textContent = "✨ Envoyer un retour privé";
              }
              if (btnGoogleReview) {
                btnGoogleReview.classList.add("btn-link-google-active");
                if (googleReviewUrl && !btnGoogleReview.disabled) {
                  btnGoogleReview.scrollIntoView({
                    behavior: "smooth",
                    block: "nearest",
                  });
                }
              }
            };
          }

          if (pillNo) {
            pillNo.onclick = () => {
              openCompactAccordionPanel("feedback");
              selectFeedback("no");
              if (commentEl) {
                commentEl.focus();
                commentEl.placeholder =
                  "Dites-nous ce qui n’a pas été satisfaisant (retour privé).";
              }
              if (helperTextEl) {
                helperTextEl.textContent =
                  "Dites-nous ce qui n’a pas été satisfaisant. Votre retour reste privé.";
              }
              if (btnFeedback) {
                btnFeedback.textContent = "✨ Envoyer mon retour";
              }
              if (btnGoogleReview) {
                btnGoogleReview.classList.remove("btn-link-google-active");
              }
            };
          }

          btnFeedback.onclick = async () => {
            if (!feedbackValue) {
              showToast("Merci de choisir un avis 😊 / 😐", true);
              return;
            }

            const sentPositive = feedbackValue === "yes";
            const comment = document.getElementById("feedback-comment").value.trim();

            try {
              const resp = await fetch(`/api/public/cards/${cardId}/feedback`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
  satisfaction: feedbackValue,   // "yes" ou "no"
  comment: comment || null
})

})

              if (!resp.ok) {
                const err = await resp.text();
                console.error("Erreur API feedback:", err);
                showToast("Impossible d’envoyer votre avis.", true);
                return;
              }

              showToast("Merci pour votre avis !");
              document.getElementById("feedback-comment").value = "";
              selectFeedback(null);
              if (btnFeedback) {
                btnFeedback.textContent = "✨ Envoyer mon avis";
              }
              if (btnGoogleReview) {
                btnGoogleReview.classList.remove("btn-link-google-active");
              }

              const nudgeEl = document.getElementById("feedback-recommend-nudge");
              if (nudgeEl) {
                if (
                  sentPositive &&
                  showRecommendBlock &&
                  (!card.owner_mode || isDemoCard)
                ) {
                  nudgeEl.hidden = false;
                  requestAnimationFrame(function () {
                    nudgeEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
                  });
                } else {
                  nudgeEl.hidden = true;
                }
              }
            } catch (e) {
              console.error(e);
              showToast("Erreur réseau lors de l’envoi de l’avis.", true);
            }
          };
        }

        const btnQuote = document.getElementById("btn-send-quote");
        if (btnQuote) {
          btnQuote.onclick = async () => {
            const name = document.getElementById("quote-name").value.trim();
            const phone = document.getElementById("quote-phone").value.trim();
            const email = document.getElementById("quote-email").value.trim();
            const message = document.getElementById("quote-message").value.trim();

            if (!name || !phone || !message) {
              showToast("Merci de remplir les champs obligatoires (*).");
              return;
            }

            try {
              const resp = await fetch(`/api/public/cards/${cardId}/quotes`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    name,
    email,
    phone,
    message,
    source_type: referrerIdFromUrl ? "recommendation" : null,
    referrer_id: referrerIdFromUrl
  })
})


              if (!resp.ok) {
                const err = await resp.text();
                console.error("Erreur API quote:", err);
                throw new Error();
              }

              showToast(CURRENT_PROFILE_CONFIG.quoteToast || "Demande envoyée !");
              trackCardEvent(analyticsSlug, "rdv_request");
              if (referrerIdFromUrl) {
                trackRecommendationEvent(
                  analyticsSlug,
                  "recommend_contact",
                  referrerIdFromUrl,
                  recommendationVisitorId
                );
              }
              document.getElementById("quote-name").value = "";
              document.getElementById("quote-phone").value = "";
              document.getElementById("quote-email").value = "";
              document.getElementById("quote-message").value = "";
              if (isWellnessMinimalTheme()) {
                closeWellnessContactModal();
              }
            } catch (e) {
              console.error(e);
              showToast("Impossible d’envoyer la demande.", true);
            }
          };
        }

        updateQrCode(analyticsSlug);

        /** Délai minimal avant navigation externe (SMS / mailto) pour laisser apparaître le toast. */
        var EXTERNAL_HANDOFF_MS = 90;

        function showToastThenHref(message, href) {
          showToast(message);
          window.setTimeout(function () {
            window.location.href = href;
          }, EXTERNAL_HANDOFF_MS);
        }

        /**
         * @param {string} url
         * @param {"card"|"recommend"} [linkKind] — « recommend » : micro-copy relationnelle post-reco.
         */
        async function copyPublicUrlToClipboard(url, linkKind) {
          var kind = linkKind === "recommend" ? "recommend" : "card";
          try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              await navigator.clipboard.writeText(url);
              if (kind === "recommend") {
                showToast(
                  "Merci — vous pouvez coller ce lien pour transmettre votre recommandation."
                );
              } else {
                showToast("Lien de la carte copié.");
              }
            } else {
              window.prompt("Copiez ce lien :", url);
            }
          } catch (e) {
            window.prompt("Copiez ce lien :", url);
          }
        }

        const btnShareMain = document.getElementById("btn-share-card-main");
        const btnShareSms = document.getElementById("btn-share-sms");
        const btnShareCopy = document.getElementById("btn-share-copy");
        const btnShareEmail = document.getElementById("btn-share-email");

        const referrerStorageKey = "smartcard_recommend_referrer_" + analyticsSlug;
        async function ensureReferrerProfileForCard() {
          return await ensureReferrerProfileForRecommendationLink(referrerStorageKey);
        }

        const shareTextNative = getOwnerShareTextNative();
        const shareTextWithLink = getOwnerShareTextWithLink();
        const shareCardTitle = getOwnerShareTitle();

        if (btnShareMain) {
          btnShareMain.onclick = async function () {
            trackCardEvent(analyticsSlug, "share_click");
            const sharePayload = {
              title: shareCardTitle,
              text: shareTextNative,
              url: cardPublicUrl
            };
            if (typeof navigator.share === "function") {
              trackCardEvent(analyticsSlug, "share_native_opened");
              try {
                await navigator.share(sharePayload);
                trackCardEvent(analyticsSlug, "share_native_success");
                showToast("Merci — votre carte accompagne ce partage.");
              } catch (err) {
                if (err && err.name === "AbortError") return;
                await copyPublicUrlToClipboard(cardPublicUrl, "card");
                trackCardEvent(analyticsSlug, "share_copy_fallback");
              }
            } else {
              await copyPublicUrlToClipboard(cardPublicUrl, "card");
              trackCardEvent(analyticsSlug, "share_copy_fallback");
            }
          };
        }

        if (btnShareSms) {
          btnShareSms.onclick = () => {
            trackCardEvent(analyticsSlug, "share_click");
            const body = encodeURIComponent(shareTextWithLink);
            const smsUrl = "sms:?&body=" + body;
            showToastThenHref("Merci — votre carte est prête dans le message.", smsUrl);
          };
        }

        if (btnShareCopy) {
          btnShareCopy.onclick = async () => {
            trackCardEvent(analyticsSlug, "share_click");
            await copyPublicUrlToClipboard(cardPublicUrl, "card");
          };
        }

        if (btnShareEmail) {
          btnShareEmail.onclick = () => {
            trackCardEvent(analyticsSlug, "share_click");
            const subject = encodeURIComponent(getOwnerEmailSubject());
            const body = encodeURIComponent(shareTextWithLink);
            const mailto = "mailto:?subject=" + subject + "&body=" + body;
            showToastThenHref("Merci — votre carte est prête dans l’e-mail.", mailto);
          };
        }

        const recommendEnabled = card.enable_recommendation === true;
        /* Démo : toujours montrer le bloc recommandation (démo produit complète). Vraie carte : selon réglage admin. */
        const showRecommendBlock = isDemoCard || recommendEnabled;
        const recommendBlock = document.getElementById("recommend-block");
        if (recommendBlock) {
          recommendBlock.style.display = showRecommendBlock ? "block" : "none";
        }

        if (showRecommendBlock) {
          const btnRecommendMain = document.getElementById("btn-recommend-main");
          const btnRecommendWellnessRow = document.getElementById("btn-recommend-wellness-row");
          const btnRecommendSms = document.getElementById("btn-recommend-sms");
          const btnRecommendCopy = document.getElementById("btn-recommend-copy");
          const btnRecommendEmail = document.getElementById("btn-recommend-email");

          async function handleRecommendMainClick() {
            const profile = await ensureReferrerProfileForCard();
            if (!profile) return;
            const referrerId = profile.referrerId;
            const recommendShareUrl =
              getPublicCardUrl(analyticsSlug) + "?r=" + encodeURIComponent(referrerId);
            const sharePayload = {
              title: getRecommendShareTitle(),
              text: getRecommendShareTextNative(),
              url: recommendShareUrl
            };
            if (typeof navigator.share === "function") {
              try {
                await navigator.share(sharePayload);
                trackCardEvent(analyticsSlug, "recommend_click");
                trackRecommendationEvent(
                  analyticsSlug,
                  "recommend_link_created",
                  referrerId,
                  null,
                  profile.firstName,
                  profile.lastName
                );
                showToast("Merci — votre recommandation accompagne ce partage.");
              } catch (err) {
                if (err && err.name === "AbortError") return;
                await copyPublicUrlToClipboard(recommendShareUrl, "recommend");
                trackCardEvent(analyticsSlug, "recommend_click");
                trackRecommendationEvent(
                  analyticsSlug,
                  "recommend_link_created",
                  referrerId,
                  null,
                  profile.firstName,
                  profile.lastName
                );
              }
            } else {
              await copyPublicUrlToClipboard(recommendShareUrl, "recommend");
              trackCardEvent(analyticsSlug, "recommend_click");
              trackRecommendationEvent(
                analyticsSlug,
                "recommend_link_created",
                referrerId,
                null,
                profile.firstName,
                profile.lastName
              );
            }
          }

          if (btnRecommendMain) {
            btnRecommendMain.onclick = handleRecommendMainClick;
          }
          if (btnRecommendWellnessRow) {
            btnRecommendWellnessRow.onclick = handleRecommendMainClick;
          }

          const btnFeedbackRecommendNudge = document.getElementById("btn-feedback-recommend-nudge");
          if (btnFeedbackRecommendNudge && (btnRecommendMain || btnRecommendWellnessRow)) {
            btnFeedbackRecommendNudge.onclick = function () {
              if (btnRecommendWellnessRow && isWellnessVisualTheme()) {
                btnRecommendWellnessRow.click();
              } else if (btnRecommendMain) {
                btnRecommendMain.click();
              }
            };
          }

          if (btnRecommendSms) {
            btnRecommendSms.onclick = async () => {
              const profile = await ensureReferrerProfileForCard();
              if (!profile) return;
              const referrerId = profile.referrerId;
              const recommendShareUrl =
                getPublicCardUrl(analyticsSlug) + "?r=" + encodeURIComponent(referrerId);
              const recommendMessage = getRecommendShareTextWithLink(recommendShareUrl);
              trackCardEvent(analyticsSlug, "recommend_share_sms");
              trackRecommendationEvent(
                analyticsSlug,
                "recommend_link_created",
                referrerId,
                null,
                profile.firstName,
                profile.lastName
              );
              showToastThenHref(
                "Merci — votre recommandation est prête dans le message.",
                "sms:?&body=" + encodeURIComponent(recommendMessage)
              );
            };
          }

          if (btnRecommendCopy) {
            btnRecommendCopy.onclick = async () => {
              const profile = await ensureReferrerProfileForCard();
              if (!profile) return;
              const referrerId = profile.referrerId;
              const recommendShareUrl =
                getPublicCardUrl(analyticsSlug) + "?r=" + encodeURIComponent(referrerId);
              trackCardEvent(analyticsSlug, "recommend_share_copy");
              trackRecommendationEvent(
                analyticsSlug,
                "recommend_link_created",
                referrerId,
                null,
                profile.firstName,
                profile.lastName
              );
              await copyPublicUrlToClipboard(recommendShareUrl, "recommend");
            };
          }

          if (btnRecommendEmail) {
            btnRecommendEmail.onclick = async () => {
              const profile = await ensureReferrerProfileForCard();
              if (!profile) return;
              const referrerId = profile.referrerId;
              const recommendShareUrl =
                getPublicCardUrl(analyticsSlug) + "?r=" + encodeURIComponent(referrerId);
              const recommendMessage = getRecommendShareTextWithLink(recommendShareUrl);
              trackCardEvent(analyticsSlug, "recommend_share_email");
              trackRecommendationEvent(
                analyticsSlug,
                "recommend_link_created",
                referrerId,
                null,
                profile.firstName,
                profile.lastName
              );
              const subject = encodeURIComponent(getRecommendEmailSubject());
              const body = encodeURIComponent(recommendMessage);
              showToastThenHref(
                "Merci — votre recommandation est prête dans l’e-mail.",
                "mailto:?subject=" + subject + "&body=" + body
              );
            };
          }
        }

        applyPublicCardUiMode(card);
        syncCompactContactSlots();
        setupHeroSocialLinks(card);
        syncCompactActionTriggers(showRecommendBlock);
        initPublicCardAccordion();

        scheduleLayoutRefresh(card);
        revealCardShell();
      } catch (e) {
        hideRecommendTrustBanner();
        console.error(e);
        showToast("Erreur lors du chargement de la carte.", true);
        revealCardShell();
      }
    }

    document.addEventListener("DOMContentLoaded", function () {
      scheduleLayoutRefresh(null);
      var q = document.getElementById("acc-trigger-quote");
      var b = document.getElementById("btn-primary-demande-contact");
      if (b) {
        b.addEventListener("click", function () {
          if (isWellnessMinimalTheme()) {
            openWellnessContactModal();
          } else if (q) {
            q.click();
          }
        });
      }
      var fa = document.getElementById("btn-cta-laisser-avis");
      var tf = document.getElementById("acc-trigger-feedback");
      if (fa && tf) fa.addEventListener("click", function () { tf.click(); });
      var br = document.getElementById("btn-cta-recommander");
      var tr = document.getElementById("acc-trigger-recommend");
      if (br && tr) br.addEventListener("click", function () { tr.click(); });
      var sd = document.getElementById("btn-discrete-partager");
      var ts = document.getElementById("acc-trigger-share");
      if (sd && ts) sd.addEventListener("click", function () { ts.click(); });
      var pd = document.getElementById("btn-discrete-paiement");
      var tp = document.getElementById("acc-trigger-pay");
      if (pd && tp) pd.addEventListener("click", function () { tp.click(); });
      loadCard();
    });

    window.addEventListener("load", function () {
      scheduleLayoutRefresh(null);
    });
