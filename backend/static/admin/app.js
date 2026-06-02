const API_BASE = "/api/cards";
const baseUrl = window.location.origin || "";
let ADMIN_API_KEY = sessionStorage.getItem("ADMIN_API_KEY") || "";
let currentCardId = null;
let currentProfile = "artisan"; // 🔹 profil courant (par défaut)
const NON_EXPIRING_PLANS = new Set(["demo", "lifetime"]);

/** Valeurs techniques visual_theme (seul champ qui pilote data-theme CSS). */
const ALLOWED_VISUAL_THEMES = new Set([
  "wellness-soft",
  "wellness-soft-minimal",
  "artisan",
  "real-estate",
  "corporate",
  "maavnica",
]);

function getVisualThemeSelect() {
  return document.getElementById("visual-theme");
}

function normalizeVisualThemeValue(value) {
  const v = (value == null ? "" : String(value)).trim().toLowerCase();
  return ALLOWED_VISUAL_THEMES.has(v) ? v : "wellness-soft";
}

function setVisualThemeSelect(value) {
  const el = getVisualThemeSelect();
  if (!el) return;
  const safe = normalizeVisualThemeValue(value);
  el.value = safe;
  if (el.value !== safe) {
    console.warn("LOAD visual_theme: valeur non reconnue, repli wellness-soft", value);
    el.value = "wellness-soft";
  }
}

function readVisualThemeFromSelect() {
  const el = getVisualThemeSelect();
  return normalizeVisualThemeValue(el && el.value ? el.value : "wellness-soft");
}

function ensureAdminApiKey() {
  if (ADMIN_API_KEY && ADMIN_API_KEY.trim()) return ADMIN_API_KEY.trim();
  const entered = window.prompt("Clé admin requise pour accéder à l’interface SmartCard :");
  if (entered === null) return "";
  ADMIN_API_KEY = entered.trim();
  if (!ADMIN_API_KEY) {
    showToast("Clé admin manquante. Actions admin bloquées.", true);
    return "";
  }
  sessionStorage.setItem("ADMIN_API_KEY", ADMIN_API_KEY);
  return ADMIN_API_KEY;
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2600);
}

async function copyTextToClipboard(text) {
  if (!text) return false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {}
  try {
    window.prompt("Copiez ce lien :", text);
    return true;
  } catch (e) {
    return false;
  }
}

/* ============================================================
   REMPLISSAGE DU FORMULAIRE
============================================================ */
function fillForm(card) {
  currentCardId = card.id;

  // Champs existants
  document.getElementById("company-name").value = card.company_name || "";
  const cityInput = document.getElementById("city");
  if (cityInput) cityInput.value = card.city || "";
document.getElementById("first-name").value = card.first_name || "";
document.getElementById("last-name").value = card.last_name || "";

  document.getElementById("slug").value = card.slug || "";
  document.getElementById("plan-type").value = card.plan_type || "demo";
  document.getElementById("region-version").value = card.region || "fr";
  setVisualThemeSelect(card.visual_theme || "wellness-soft");
  document.getElementById("expires-at").value = toDatetimeLocalValue(card.expires_at);
  document.getElementById("existing-slug").value = card.slug || "";
  document.getElementById("google-link").value = card.google_review_link || "";
  document.getElementById("google-rating").value = card.google_rating != null ? card.google_rating : "";
  document.getElementById("google-review-count").value = card.google_review_count != null ? card.google_review_count : "";
  document.getElementById("phone").value = card.phone || "";
  document.getElementById("whatsapp").value = card.whatsapp || "";
  document.getElementById("payment-link").value = card.payment_link || "";
  document.getElementById("instagram").value = card.instagram || "";
  document.getElementById("facebook").value = card.facebook || "";
  document.getElementById("tiktok").value = card.tiktok || "";

  // 🔹 NOUVEAUX CHAMPS
  document.getElementById("profile").value = card.profile || "artisan";
  document.getElementById("email-pro").value = card.email_pro || "";
  document.getElementById("site-web").value = card.site_web || "";
  document.getElementById("avatar-url").value = card.avatar_url || "";
  document.getElementById("hero-title").value = card.hero_title || "";
  document.getElementById("hero-text").value = card.hero_text || "";
  document.getElementById("hero-cta-text").value = card.hero_cta_text || "";
  document.getElementById("display-name").value = card.display_name || "";
  document.getElementById("business-name-field").value = card.business_name || "";
  document.getElementById("job-title").value = card.job_title || "";
  document.getElementById("form-title").value = card.form_title || "";
  const recCb = document.getElementById("enable-recommendation");
  if (recCb) recCb.checked = !!card.enable_recommendation;
  const recCodeEl = document.getElementById("recommendation-code");
  if (recCodeEl) recCodeEl.value = card.recommendation_code || "";
  const ownerKeyEl = document.getElementById("owner-share-key");
  if (ownerKeyEl) ownerKeyEl.value = card.owner_share_key || "";

  // 🔹 On mémorise le profil pour adapter les libellés dans l’admin
  currentProfile = card.profile || "artisan";
  updatePlanExpirationUI(false);

  updatePublicLink();
}

/* ============================================================
   RESET DU FORMULAIRE
============================================================ */
function resetForm() {
  currentCardId = null;
  currentProfile = "artisan";

  // Champs existants
  document.getElementById("company-name").value = "";
  const cityInputReset = document.getElementById("city");
  if (cityInputReset) cityInputReset.value = "";
document.getElementById("first-name").value = "";
document.getElementById("last-name").value = "";

  document.getElementById("slug").value = "";
  document.getElementById("plan-type").value = "demo";
  document.getElementById("region-version").value = "fr";
  setVisualThemeSelect("wellness-soft");
  document.getElementById("expires-at").value = "";
  document.getElementById("existing-slug").value = "";
  document.getElementById("google-link").value = "";
  document.getElementById("google-rating").value = "";
  document.getElementById("google-review-count").value = "";
  document.getElementById("phone").value = "";
  document.getElementById("whatsapp").value = "";
  document.getElementById("payment-link").value = "";
  document.getElementById("instagram").value = "";
  document.getElementById("facebook").value = "";
  document.getElementById("tiktok").value = "";

  // 🔹 nouveaux champs
  document.getElementById("profile").value = "artisan";
  document.getElementById("email-pro").value = "";
  document.getElementById("site-web").value = "";
  document.getElementById("avatar-url").value = "";
  document.getElementById("hero-title").value = "";
  document.getElementById("hero-text").value = "";
  document.getElementById("hero-cta-text").value = "";
  document.getElementById("display-name").value = "";
  document.getElementById("business-name-field").value = "";
  document.getElementById("job-title").value = "";
  document.getElementById("form-title").value = "";
  const recCbReset = document.getElementById("enable-recommendation");
  if (recCbReset) recCbReset.checked = false;
  const recCodeReset = document.getElementById("recommendation-code");
  if (recCodeReset) recCodeReset.value = "";
  const ownerKeyReset = document.getElementById("owner-share-key");
  if (ownerKeyReset) ownerKeyReset.value = "";
  const avatarFile = document.getElementById("avatar-file");
  if (avatarFile) avatarFile.value = "";

  document.getElementById("public-link").textContent = "";
  const ownerLinkBox = document.getElementById("owner-public-link");
  if (ownerLinkBox) ownerLinkBox.textContent = "";
  document.getElementById("feedback-list").innerHTML =
    '<div class="hint">Aucun avis pour l’instant.</div>';
  document.getElementById("quote-list").innerHTML =
    '<div class="hint">Aucune demande pour l’instant.</div>';
  const cardsList = document.getElementById("cards-list");
  if (cardsList) cardsList.innerHTML = '<div class="hint">Aucune carte chargée.</div>';
  updatePlanExpirationUI(false);
}

function toDatetimeLocalValue(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return "";
  const tzOffset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
}

function computeDefaultExpiration(planType) {
  const now = new Date();
  if (planType === "trial") now.setDate(now.getDate() + 30);
  else if (planType === "solo" || planType === "business") now.setFullYear(now.getFullYear() + 1);
  else return "";
  const tzOffset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - tzOffset).toISOString().slice(0, 16);
}

function updatePlanExpirationUI(autoPrefill = true) {
  const plan = document.getElementById("plan-type").value;
  const expiresInput = document.getElementById("expires-at");
  const hint = document.getElementById("plan-expiration-hint");
  if (NON_EXPIRING_PLANS.has(plan)) {
    expiresInput.value = "";
    expiresInput.disabled = true;
    expiresInput.required = false;
    if (hint) hint.textContent = "Sans expiration pour demo/lifetime.";
    return;
  }
  expiresInput.disabled = false;
  expiresInput.required = true;
  if (autoPrefill && !expiresInput.value) {
    expiresInput.value = computeDefaultExpiration(plan);
  }
  if (hint) hint.textContent = "Expiration requise pour trial/solo/business.";
}

/* ============================================================
   AFFICHAGE DU LIEN PUBLIC
============================================================ */
/** Lien public client : /c/{slug} (sans query). */
function publicCardUrlForSlug(slug) {
  const s = (slug || "").trim();
  if (!s) return "";
  return `${baseUrl}/c/${encodeURIComponent(s)}`;
}

/** Prévisualisation admin : n’impacte pas les analytics publiques. */
function adminPreviewUrlForSlug(slug) {
  const pub = publicCardUrlForSlug(slug);
  if (!pub) return "";
  return pub + "?admin_view=1";
}

function updatePublicLink() {
  const slug = document.getElementById("slug").value.trim();
  const box = document.getElementById("public-link");
  const ownerBox = document.getElementById("owner-public-link");

  if (!slug) {
    box.textContent = "";
    if (ownerBox) ownerBox.textContent = "";
    return;
  }

  const publicUrl = `${baseUrl}/c/${encodeURIComponent(slug)}`;
  box.textContent = publicUrl;

  if (ownerBox) {
    const ok = (document.getElementById("owner-share-key")?.value || "").trim();
    if (ok) {
      ownerBox.textContent = `${baseUrl}/c/${encodeURIComponent(slug)}?o=${encodeURIComponent(ok)}`;
    } else {
      ownerBox.textContent =
        "Chargez ou enregistrez la carte pour générer le lien personnel.";
    }
  }
}

function getComputedPublicLink() {
  const slug = document.getElementById("slug")?.value.trim() || "";
  return publicCardUrlForSlug(slug);
}

function getComputedAdminPreviewLink() {
  const slug = document.getElementById("slug")?.value.trim() || "";
  return adminPreviewUrlForSlug(slug);
}

function openAdminCardPreview() {
  const url = getComputedAdminPreviewLink();
  if (!url) {
    showToast("Prévisualisation impossible sans slug.", true);
    return;
  }
  window.open(url, "_blank", "noopener");
}

function getComputedOwnerLink() {
  const publicUrl = getComputedPublicLink();
  const ownerKey = (document.getElementById("owner-share-key")?.value || "").trim();
  if (!publicUrl || !ownerKey) return "";
  return publicUrl + "?o=" + encodeURIComponent(ownerKey);
}

async function copyOwnerLink() {
  const ownerLink = getComputedOwnerLink();
  if (!ownerLink) {
    showToast("Lien personnel indisponible. Chargez ou enregistrez la carte.", true);
    return;
  }
  const ok = await copyTextToClipboard(ownerLink);
  if (ok) showToast("Lien personnel copié.");
}

async function copyPublicLink() {
  const publicLink = getComputedPublicLink();
  if (!publicLink) {
    showToast("Lien public indisponible. Renseignez le slug.", true);
    return;
  }
  const ok = await copyTextToClipboard(publicLink);
  if (ok) showToast("Lien public copié.");
}

/* ============================================================
   CHARGER UNE CARTE PAR SLUG
============================================================ */
async function loadCardBySlug() {
  const slug = document.getElementById("existing-slug").value.trim();

  if (!slug) {
    showToast("Merci de renseigner un slug.", true);
    return;
  }

  const adminKey = ensureAdminApiKey();
  if (!adminKey) return;

  try {
    const res = await fetch(`${API_BASE}/by-slug/${encodeURIComponent(slug)}`, {
      headers: { "Authorization": "Bearer " + adminKey }
    });
    if (!res.ok) {
      showToast("Carte introuvable pour ce slug.", true);
      return;
    }

    const data = await res.json();
    fillForm(data);
    showToast("Carte chargée.");
    await loadFeedbackAndQuotes();
  } catch (err) {
    console.error(err);
    showToast("Erreur réseau lors du chargement.", true);
  }
}

async function loadCardFromQueryParam() {
  const params = new URLSearchParams(window.location.search || "");
  const slug = (params.get("slug") || "").trim();
  if (!slug) return;
  const slugInput = document.getElementById("existing-slug");
  if (!slugInput) return;
  slugInput.value = slug;
  await loadCardBySlug();
}

/* ============================================================
   SAUVEGARDE (CREATE / UPDATE)
============================================================ */
async function saveCard() {
  const companyName = document.getElementById("company-name").value.trim();
  let slug = document.getElementById("slug").value.trim();

  if (!companyName || !slug) {
    showToast("Nom d’entreprise et slug sont obligatoires.", true);
    return;
  }

  const adminKey = ensureAdminApiKey();
  if (!adminKey) return;

  slug = slug.toLowerCase();
  document.getElementById("slug").value = slug;
  document.getElementById("existing-slug").value = slug;

  // Payload admin : visual_theme (CSS) + profile (métier) uniquement.
  // theme / card_theme / theme_color : colonnes BDD conservées, non envoyées depuis l’admin.
  const payload = {
 first_name: document.getElementById("first-name")?.value.trim() || null,
  last_name: document.getElementById("last-name")?.value.trim() || null,
    company_name: companyName,
    city: (document.getElementById("city")?.value ?? "").trim() || null,
    slug,
    plan_type: document.getElementById("plan-type").value || "demo",
    region: (() => {
      const el = document.getElementById("region-version");
      const v = el && el.value ? el.value.trim().toLowerCase() : "";
      return v === "latam" ? "latam" : "fr";
    })(),
    visual_theme: readVisualThemeFromSelect(),
    expires_at: (() => {
      const v = document.getElementById("expires-at").value;
      return v ? new Date(v).toISOString() : null;
    })(),

    // 🔹 Champs classiques
    google_review_link: document.getElementById("google-link").value.trim() || null,
    google_rating: (() => {
      const v = document.getElementById("google-rating").value.trim();
      if (!v) return null;
      const n = parseFloat(v);
      return isNaN(n) ? null : n;
    })(),
    google_review_count: (() => {
      const v = document.getElementById("google-review-count").value.trim();
      if (!v) return null;
      const n = parseInt(v, 10);
      return isNaN(n) ? null : n;
    })(),
    phone: document.getElementById("phone").value.trim() || null,
    whatsapp: document.getElementById("whatsapp").value.trim() || null,
    payment_link: document.getElementById("payment-link").value.trim() || null,
    instagram: document.getElementById("instagram").value.trim() || null,
    facebook: document.getElementById("facebook").value.trim() || null,
    tiktok: document.getElementById("tiktok").value.trim() || null,

    // 🔹 NOUVEAUX CHAMPS
    profile: document.getElementById("profile").value || "artisan",
    email_pro: document.getElementById("email-pro").value.trim() || null,
    site_web: document.getElementById("site-web").value.trim() || null,
    avatar_url: document.getElementById("avatar-url").value.trim() || null,
    hero_title: document.getElementById("hero-title").value.trim() || null,
    hero_text: document.getElementById("hero-text").value.trim() || null,
    hero_cta_text: document.getElementById("hero-cta-text").value.trim() || null,

    display_name: document.getElementById("display-name").value.trim() || null,
    business_name:
      document.getElementById("business-name-field").value.trim() || null,
    job_title: document.getElementById("job-title").value.trim() || null,
    form_title: document.getElementById("form-title").value.trim() || null,

    enable_recommendation: !!document.getElementById("enable-recommendation")?.checked,
    recommendation_code:
      document.getElementById("recommendation-code")?.value.trim() || null
  };
  if (NON_EXPIRING_PLANS.has(payload.plan_type)) {
    payload.expires_at = null;
  }

  // on met aussi à jour currentProfile si on change dans le formulaire
  currentProfile = payload.profile || "artisan";

  console.log("SAVE visual_theme", payload.visual_theme, "| profile", payload.profile);

  const btn = document.getElementById("btn-save");
  btn.disabled = true;
  btn.textContent = "Enregistrement…";

  try {
    let url = API_BASE + "/";
    let method = "POST";

    if (currentCardId) {
      url = `${API_BASE}/${currentCardId}`;
      method = "PUT";
    }

    const res = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + adminKey
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("Erreur API:", res.status, text);
      showToast("Erreur lors de l’enregistrement.", true);
      return;
    }

    const data = await res.json();
    fillForm(data);
    showToast("Carte enregistrée.");

    await loadFeedbackAndQuotes();
  } catch (err) {
    console.error(err);
    showToast("Erreur réseau lors de l’enregistrement.", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Enregistrer la carte";
  }
}

function formatExpiration(card) {
  if (!card.expires_at || NON_EXPIRING_PLANS.has((card.plan_type || "").toLowerCase())) {
    return "Sans expiration";
  }
  const d = new Date(card.expires_at);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

async function loadAllCards() {
  const adminKey = ensureAdminApiKey();
  if (!adminKey) return;
  const box = document.getElementById("cards-list");
  if (!box) return;
  try {
    const res = await fetch(`${API_BASE}/`, {
      headers: { "Authorization": "Bearer " + adminKey }
    });
    if (!res.ok) {
      box.innerHTML = '<div class="hint">Impossible de charger la liste.</div>';
      return;
    }
    const cards = await res.json();
    if (!cards.length) {
      box.innerHTML = '<div class="hint">Aucune carte pour le moment.</div>';
      return;
    }
    box.innerHTML = `
      <table class="cards-table">
        <thead>
          <tr>
            <th>Slug</th><th>Plan</th><th>Région</th><th>Expiration</th><th>Statut</th><th>Jours restants</th>
            <th>Prévisualiser</th>
          </tr>
        </thead>
        <tbody>
          ${cards.map((c) => `
            <tr data-slug="${c.slug}" class="card-row">
              <td>${c.slug}</td>
              <td>${c.plan_type || "demo"}</td>
              <td>${c.region || "fr"}</td>
              <td>${formatExpiration(c)}</td>
              <td><span class="status-badge ${c.computed_status === "expired" ? "status-expired" : "status-active"}">${c.computed_status || "active"}</span></td>
              <td>${c.days_remaining == null ? "—" : c.days_remaining}</td>
              <td><a href="${adminPreviewUrlForSlug(c.slug)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Ouvrir</a></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
    box.querySelectorAll(".card-row").forEach((row) => {
      row.addEventListener("click", () => {
        const slug = row.getAttribute("data-slug");
        document.getElementById("existing-slug").value = slug;
        loadCardBySlug();
      });
    });
  } catch (e) {
    box.innerHTML = '<div class="hint">Erreur réseau pendant le chargement.</div>';
  }
}

/* ============================================================
   CHARGEMENT AVIS + DEMANDES (devis / rdv / réservation...)
============================================================ */
async function loadFeedbackAndQuotes() {
  if (!currentCardId) return;

  const adminKey = ensureAdminApiKey();
  if (!adminKey) return;

  try {
    const [fRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/${currentCardId}/feedback`, {
        headers: { "Authorization": "Bearer " + adminKey }
      }),
      fetch(`${API_BASE}/${currentCardId}/quotes`, {
        headers: { "Authorization": "Bearer " + adminKey }
      })
    ]);

    const feedbackList = document.getElementById("feedback-list");
    const quoteList = document.getElementById("quote-list");

    console.log("Admin SmartCard – profil courant pour libellé :", currentProfile);

    // Avis
    if (fRes.ok) {
      const items = await fRes.json();
      if (!items.length) {
        feedbackList.innerHTML =
          '<div class="hint">Aucun avis pour l’instant.</div>';
      } else {
        feedbackList.innerHTML = items
          .map(
            (f) => `
          <div class="item">
            <div class="item-title">${
              f.satisfaction ? "🙂 Satisfait" : "🙁 Pas satisfait"
            }</div>
            ${f.comment ? `<div>${f.comment}</div>` : ""}
            <div class="item-meta">${new Date(
              f.created_at
            ).toLocaleString()}</div>
          </div>
        `
          )
          .join("");
      }
    }

    // 🔹 Déterminer le bon libellé en fonction du profil
    let baseLabel = "Demande de devis";
    const p = (currentProfile || "artisan").toLowerCase();

    if (p === "resto" || p === "restaurant") {
      baseLabel = "Demande de réservation";
    } else if (p === "medical" || p === "bien_etre" || p === "sante") {
      baseLabel = "Demande de rendez-vous";
    } else if (p === "digital") {
      baseLabel = "Demande de contact";
    } else if (p === "immo") {
      baseLabel = "Demande de visite / estimation";
    } else {
      baseLabel = "Demande de devis";
    }

    // Devis / demandes
    if (qRes.ok) {
      const items = await qRes.json();
      if (!items.length) {
        quoteList.innerHTML =
          '<div class="hint">Aucune demande pour l’instant.</div>';
      } else {
        quoteList.innerHTML = items
          .map(
            (q) => `
          <div class="item">
            <div class="item-title">${baseLabel} – ${q.name || "—"}</div>
            <div>${q.phone || ""}${q.email ? " · " + q.email : ""}</div>
            <div>${q.message || ""}</div>
            <div><strong>Origine :</strong> ${
              q.source_type === "recommendation" ? "recommandation" : "directe / autre"
            }</div>
            <div><strong>Recommandé par :</strong> ${(() => {
              const d = (q.recommender_display_name || "").trim();
              if (d) return d;
              const rid = (q.referrer_id || "").trim();
              if (!rid) return "—";
              if (rid.toLowerCase().startsWith("rec_")) return "—";
              return rid;
            })()}</div>
            <div class="item-meta">${new Date(
              q.created_at
            ).toLocaleString()}</div>
          </div>
        `
          )
          .join("");
      }
    }
  } catch (err) {
    console.error(err);
  }
}

/* ============================================================
   LISTENERS
============================================================ */
/* ============================================================
   UPLOAD AVATAR (fichier → URL)
============================================================ */
const UPLOAD_AVATAR_URL = "/api/upload/avatar";
const ALLOWED_AVATAR_EXT = [".jpg", ".jpeg", ".png", ".webp"];

function hasAllowedAvatarExt(filename) {
  if (!filename) return false;
  const ext = "." + (filename.split(".").pop() || "").toLowerCase();
  return ALLOWED_AVATAR_EXT.includes(ext);
}

async function uploadAvatarFile(file) {
  const adminKey = ensureAdminApiKey();
  if (!adminKey) throw new Error("Clé admin requise.");
  const res = await fetch(UPLOAD_AVATAR_URL, {
    method: "POST",
    headers: { "Authorization": "Bearer " + adminKey },
    body: (() => {
      const fd = new FormData();
      fd.append("file", file);
      return fd;
    })(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Échec de l’upload.");
  }
  return res.json();
}

function initAvatarUpload() {
  const fileInput = document.getElementById("avatar-file");
  const urlInput = document.getElementById("avatar-url");
  if (!fileInput || !urlInput) return;

  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (!hasAllowedAvatarExt(file.name)) {
      showToast("Format non accepté. Utilisez : .jpg, .jpeg, .png ou .webp", true);
      fileInput.value = "";
      return;
    }
    try {
      const data = await uploadAvatarFile(file);
      urlInput.value = data.url || "";
      showToast("Image envoyée. Pensez à enregistrer la carte.");
      fileInput.value = "";
    } catch (err) {
      showToast(err.message || "Erreur lors de l’upload.", true);
      fileInput.value = "";
    }
  });
}

/* ============================================================
   LISTENERS
============================================================ */
document.getElementById("btn-load").addEventListener("click", loadCardBySlug);
document.getElementById("btn-save").addEventListener("click", saveCard);
document.getElementById("btn-reset").addEventListener("click", resetForm);
document.getElementById("slug").addEventListener("input", updatePublicLink);
document.getElementById("plan-type").addEventListener("change", () => updatePlanExpirationUI(true));
document.getElementById("btn-copy-owner-link").addEventListener("click", copyOwnerLink);
document.getElementById("btn-copy-public-link").addEventListener("click", copyPublicLink);
const btnOpenPreview = document.getElementById("btn-open-preview");
if (btnOpenPreview) btnOpenPreview.addEventListener("click", openAdminCardPreview);
document.getElementById("btn-refresh-cards").addEventListener("click", loadAllCards);
initAvatarUpload();
updatePlanExpirationUI(false);
loadAllCards();
loadCardFromQueryParam();



