const API_BASE = "/api/cards";
let currentCardId = null;
let currentProfile = "artisan"; // 🔹 profil courant (par défaut)

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2600);
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
  const avatarFile = document.getElementById("avatar-file");
  if (avatarFile) avatarFile.value = "";

  document.getElementById("public-link").textContent = "";
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

  if (!slug) {
    box.textContent = "";
    return;
  }

  const base = window.location.origin;
  box.textContent = "Lien public : " + base.replace(/\/admin$/, "") + "/c/" + slug;
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

  try {
    const res = await fetch(`${API_BASE}/by-slug/${encodeURIComponent(slug)}`);
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
    avatar_url: document.getElementById("avatar-url").value.trim() || null
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

    console.warn("[DEBUG] saveCard payload keys:", Object.keys(payload), "avatar_url:", payload.avatar_url);

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
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

  try {
    const [fRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/${currentCardId}/feedback`),
      fetch(`${API_BASE}/${currentCardId}/quotes`)
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
  const res = await fetch(UPLOAD_AVATAR_URL, {
    method: "POST",
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
initAvatarUpload();



