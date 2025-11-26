const API_BASE = "/api/cards";
let currentCardId = null;

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2600);
}

function fillForm(card) {
  currentCardId = card.id;
  document.getElementById("company-name").value = card.company_name || "";
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

  updatePublicLink();
}

function resetForm() {
  currentCardId = null;
  document.getElementById("company-name").value = "";
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
  document.getElementById("public-link").textContent = "";
  document.getElementById("feedback-list").innerHTML = '<div class="hint">Aucun avis pour l’instant.</div>';
  document.getElementById("quote-list").innerHTML = '<div class="hint">Aucune demande pour l’instant.</div>';
}

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

  const payload = {
    company_name: companyName,
    slug,
    google_review_link: document.getElementById("google-link").value.trim() || null,
    phone: document.getElementById("phone").value.trim() || null,
    whatsapp: document.getElementById("whatsapp").value.trim() || null,
    payment_link: document.getElementById("payment-link").value.trim() || null,
    instagram: document.getElementById("instagram").value.trim() || null,
    facebook: document.getElementById("facebook").value.trim() || null,
    tiktok: document.getElementById("tiktok").value.trim() || null,
    theme: document.getElementById("theme").value || "apple",
    theme_color: document.getElementById("theme-color").value.trim() || "#2563EB"
  };

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

async function loadFeedbackAndQuotes() {
  if (!currentCardId) return;

  try {
    const [fRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/${currentCardId}/feedback`),
      fetch(`${API_BASE}/${currentCardId}/quotes`)
    ]);

    const feedbackList = document.getElementById("feedback-list");
    const quoteList = document.getElementById("quote-list");

    // Avis
    if (fRes.ok) {
      const items = await fRes.json();
      if (!items.length) {
        feedbackList.innerHTML = '<div class="hint">Aucun avis pour l’instant.</div>';
      } else {
        feedbackList.innerHTML = items.map(f => `
          <div class="item">
            <div class="item-title">${f.satisfaction ? "🙂 Satisfait" : "🙁 Pas satisfait"}</div>
            ${f.comment ? `<div>${f.comment}</div>` : ""}
            <div class="item-meta">${new Date(f.created_at).toLocaleString()}</div>
          </div>
        `).join("");
      }
    }

    // Devis
    if (qRes.ok) {
      const items = await qRes.json();
      if (!items.length) {
        quoteList.innerHTML = '<div class="hint">Aucune demande pour l’instant.</div>';
      } else {
        quoteList.innerHTML = items.map(q => `
          <div class="item">
            <div class="item-title">Demande de ${q.name || "—"}</div>
            <div>${q.phone || ""} ${q.email ? " · " + q.email : ""}</div>
            <div>${q.message || ""}</div>
            <div class="item-meta">${new Date(q.created_at).toLocaleString()}</div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error(err);
  }
}

// LISTENERS
document.getElementById("btn-load").addEventListener("click", loadCardBySlug);
document.getElementById("btn-save").addEventListener("click", saveCard);
document.getElementById("btn-reset").addEventListener("click", resetForm);
document.getElementById("slug").addEventListener("input", updatePublicLink);
