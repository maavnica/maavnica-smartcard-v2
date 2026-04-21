const API_BASE = "/api/cards";
let ADMIN_API_KEY = sessionStorage.getItem("ADMIN_API_KEY") || "";
let currentCardId = null;
let currentProfile = "artisan"; // 🔹 profil courant (par défaut)

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
document.getElementById("first-name").value = card.first_name || "";
document.getElementById("last-name").value = card.last_name || "";

  document.getElementById("slug").value = card.slug || "";
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
  document.getElementById("theme-color").value = card.theme_color || "#2563EB";
  document.getElementById("theme").value = card.theme || "apple";

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
document.getElementById("first-name").value = "";
document.getElementById("last-name").value = "";

  document.getElementById("slug").value = "";
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
  document.getElementById("theme-color").value = "#2563EB";
  document.getElementById("theme").value = "apple";

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
}

/* ============================================================
   AFFICHAGE DU LIEN PUBLIC
============================================================ */
function updatePublicLink() {
  const slug = document.getElementById("slug").value.trim();
  const box = document.getElementById("public-link");
  const ownerBox = document.getElementById("owner-public-link");

  if (!slug) {
    box.textContent = "";
    if (ownerBox) ownerBox.textContent = "";
    return;
  }

  const base = window.location.origin;
  const origin = base.replace(/\/admin$/, "");
  const publicUrl = origin + "/c/" + slug;
  box.textContent = publicUrl;

  if (ownerBox) {
    const ok = (document.getElementById("owner-share-key")?.value || "").trim();
    if (ok) {
      ownerBox.textContent = publicUrl + "?o=" + encodeURIComponent(ok);
    } else {
      ownerBox.textContent =
        "Chargez ou enregistrez la carte pour générer le lien personnel.";
    }
  }
}

function getComputedPublicLink() {
  const slug = document.getElementById("slug")?.value.trim() || "";
  if (!slug) return "";
  const origin = window.location.origin.replace(/\/admin$/, "");
  return origin + "/c/" + slug;
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

  // Payload envoyé au backend
  const payload = {
 first_name: document.getElementById("first-name")?.value.trim() || null,
  last_name: document.getElementById("last-name")?.value.trim() || null,
    company_name: companyName,
    slug,

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
    theme: document.getElementById("theme").value || "apple",
    theme_color: document.getElementById("theme-color").value.trim() || "#2563EB",

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

  // on met aussi à jour currentProfile si on change dans le formulaire
  currentProfile = payload.profile || "artisan";

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
            <div><strong>Recommandé par :</strong> ${q.referrer_id || "—"}</div>
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
document.getElementById("btn-copy-owner-link").addEventListener("click", copyOwnerLink);
document.getElementById("btn-copy-public-link").addEventListener("click", copyPublicLink);
initAvatarUpload();



