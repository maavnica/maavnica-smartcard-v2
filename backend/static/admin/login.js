const form = document.getElementById("admin-login-form");
const passwordInput = document.getElementById("admin-password");
const errorBox = document.getElementById("login-error");
const submitButton = form.querySelector('button[type="submit"]');

function safeAdminDestination() {
  const candidate = new URLSearchParams(window.location.search).get("next") || "/admin";
  return candidate.startsWith("/admin") && !candidate.startsWith("//")
    ? candidate
    : "/admin";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.textContent = "";
  const password = passwordInput.value;
  if (!password) {
    errorBox.textContent = "Saisissez votre mot de passe administrateur.";
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Connexion…";
  try {
    const response = await fetch("/api/admin/session/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    passwordInput.value = "";
    if (response.ok) {
      window.location.replace(safeAdminDestination());
      return;
    }
    if (response.status === 429) {
      errorBox.textContent = "Trop de tentatives. Réessayez dans quelques minutes.";
    } else if (response.status === 401) {
      errorBox.textContent = "Mot de passe administrateur incorrect.";
    } else {
      errorBox.textContent = "Connexion indisponible. Réessayez ultérieurement.";
    }
  } catch (error) {
    passwordInput.value = "";
    errorBox.textContent = "Impossible de joindre le serveur.";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Se connecter";
  }
});
