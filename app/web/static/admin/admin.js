const loadingState = document.querySelector("#loading-state");
const disconnectedState = document.querySelector("#disconnected-state");
const connectedState = document.querySelector("#connected-state");
const adminError = document.querySelector("#admin-error");
const streamerAvatar = document.querySelector("#streamer-avatar");
const avatarFallback = document.querySelector("#avatar-fallback");
const streamerDisplayName = document.querySelector("#streamer-display-name");
const streamerLogin = document.querySelector("#streamer-login");
const activeStreamer = document.querySelector("#active-streamer");
const botLogin = document.querySelector("#bot-login");
const chatStatus = document.querySelector("#chat-status");
const overlayUrlInput = document.querySelector("#overlay-url");
const copyOverlayUrlButton = document.querySelector("#copy-overlay-url");
const copyButtonLabel = copyOverlayUrlButton.querySelector("span");
const copyStatus = document.querySelector("#copy-status");
const overlayAccessBadge = document.querySelector("#overlay-access-badge");
const overlayAccessLabel = document.querySelector("#overlay-access-label");
const overlayRotatedAt = document.querySelector("#overlay-rotated-at");
const rotateOverlayAccessButton = document.querySelector(
  "#rotate-overlay-access",
);
const rotateOverlayAccessLabel = document.querySelector(
  "#rotate-overlay-access-label",
);
const logoutButton = document.querySelector("#logout-button");
const retryButton = document.querySelector("#retry-button");
const logoutStatus = document.querySelector("#logout-status");

let overlayAccessConfigured = false;

const chatStatusLabels = {
  ready: "Opérationnel",
  degraded: "Dégradé",
  disabled: "Désactivé",
};
copyOverlayUrlButton.addEventListener("click", async () => {
  copyStatus.textContent = "";
  copyStatus.classList.remove("feedback-error");

  try {
    await navigator.clipboard.writeText(overlayUrlInput.value);
    copyButtonLabel.textContent = "Copiée";
    copyStatus.textContent = "URL copiée dans le presse-papiers.";

    window.setTimeout(() => {
      copyButtonLabel.textContent = "Copier";
    }, 2000);
  } catch {
    overlayUrlInput.focus();
    overlayUrlInput.select();
    copyStatus.textContent = "Copie impossible. L'URL a été sélectionnée pour une copie manuelle.";
    copyStatus.classList.add("feedback-error");
  }
});

rotateOverlayAccessButton.addEventListener("click", async () => {
  if (overlayAccessConfigured) {
    const confirmed = window.confirm(
      "Régénérer ce lien invalidera immédiatement l’ancienne source OBS. Continuer ?",
    );

    if (!confirmed) {
      return;
    }
  }

  rotateOverlayAccessButton.disabled = true;
  copyOverlayUrlButton.disabled = true;
  overlayUrlInput.value = "";
  copyStatus.classList.remove("feedback-error");
  copyStatus.textContent = overlayAccessConfigured
    ? "Régénération du lien sécurisé…"
    : "Génération du lien sécurisé…";

  try {
    const response = await fetch(
      "/api/admin/plugins/giveaway/overlay-access/rotate",
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (response.status === 401) {
      showDisconnectedState();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to rotate the overlay access key");
    }

    const data = await response.json();

    if (typeof data.overlay_url !== "string" || !data.overlay_url) {
      throw new Error("Missing overlay URL");
    }

    const overlayUrl = new URL(data.overlay_url);
    if (
      overlayUrl.origin !== window.location.origin ||
      overlayUrl.pathname !== "/plugins/giveaway/overlay" ||
      !overlayUrl.hash
    ) {
      throw new Error("Invalid overlay URL");
    }

    await loadOverlayAccessStatus();

    overlayUrlInput.value = overlayUrl.href;
    copyOverlayUrlButton.disabled = false;
    copyStatus.classList.remove("feedback-error");
    copyStatus.textContent =
      "Nouveau lien prêt. Copiez-le maintenant : il ne sera plus affiché après rechargement.";
  } catch {
    copyStatus.textContent =
      "Impossible de générer le lien OBS. Réessayez plus tard.";
    copyStatus.classList.add("feedback-error");
  } finally {
    rotateOverlayAccessButton.disabled = false;
  }
});

retryButton.addEventListener("click", () => {
  window.location.reload();
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  logoutStatus.textContent = "";

  try {
    const response = await fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      }
    });

    if (response.status !== 204) {
      throw new Error("Unable to close the admin session");
    }

    window.location.reload();
  } catch {
    logoutButton.disabled = false;
    logoutStatus.textContent = "Impossible de fermer la session. Réessayez plus tard.";
  }
});

function showDisconnectedState() {
  loadingState.hidden = true;
  disconnectedState.hidden = false;
  connectedState.hidden = true;
  adminError.hidden = true;
}

function showErrorState() {
  loadingState.hidden = true;
  disconnectedState.hidden = true;
  connectedState.hidden = true;
  adminError.hidden = false;
}

function showConnectedState(data) {
  const session = data.session;

  streamerDisplayName.textContent = session.display_name;
  streamerLogin.textContent = `@${session.login}`;
  chatStatus.textContent = chatStatusLabels[data.chat.status] ?? "Inconnu";
  chatStatus.dataset.status = data.chat.status;

  if (session.profile_image_url) {
    streamerAvatar.src = session.profile_image_url;
    streamerAvatar.alt = `Avatar Twitch de ${session.display_name}`;
    streamerAvatar.hidden = false;
    avatarFallback.hidden = true;
  } else {
    streamerAvatar.removeAttribute("src");
    streamerAvatar.alt = "";
    streamerAvatar.hidden = true;
    avatarFallback.hidden = false;
  }

  if (data.active_streamer === null) {
    activeStreamer.textContent = "Aucun streamer actif";
  } else {
    activeStreamer.textContent =
      `${data.active_streamer.display_name} ` +
      `(@${data.active_streamer.login})`;
  }

  botLogin.textContent = `@${data.bot.login}`;

  loadingState.hidden = true;
  disconnectedState.hidden = true;
  connectedState.hidden = false;
  adminError.hidden = true;
}

streamerAvatar.addEventListener("error", () => {
  streamerAvatar.hidden = true;
  avatarFallback.hidden = false;
});

function renderOverlayAccessStatus(data) {
  overlayAccessConfigured = data.configured === true;

  overlayAccessBadge.classList.toggle(
    "status-success",
    overlayAccessConfigured,
  );
  overlayAccessBadge.classList.toggle(
    "status-neutral",
    !overlayAccessConfigured,
  );

  overlayAccessLabel.textContent = overlayAccessConfigured
    ? "Lien configuré"
    : "Aucun lien configuré";

  rotateOverlayAccessLabel.textContent = overlayAccessConfigured
    ? "Régénérer le lien"
    : "Générer le lien";

  if (overlayAccessConfigured && data.rotated_at) {
    const rotatedAt = new Date(data.rotated_at);

    overlayRotatedAt.textContent =
      `Dernière rotation : ${rotatedAt.toLocaleString("fr-FR", {
        dateStyle: "medium",
        timeStyle: "short",
      })}`;
  } else {
    overlayRotatedAt.textContent = "Aucune clé OBS active.";
  }

  overlayUrlInput.value = "";
  copyOverlayUrlButton.disabled = true;
  rotateOverlayAccessButton.disabled = false;

  copyStatus.textContent = "";
  copyStatus.classList.remove("feedback-error");
}

async function loadOverlayAccessStatus() {
  try {
    const response = await fetch(
      "/api/admin/plugins/giveaway/overlay-access",
      {
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (response.status === 401) {
      showDisconnectedState();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to load the overlay access status");
    }

    const data = await response.json();
    renderOverlayAccessStatus(data);
  } catch {
    overlayAccessLabel.textContent = "Statut indisponible";
    overlayRotatedAt.textContent = "Impossible de vérifier la clé OBS.";
    rotateOverlayAccessButton.disabled = true;

    copyStatus.textContent = "Impossible de charger l’accès OBS.";
    copyStatus.classList.add("feedback-error");
  }
}

async function loadAdminSession() {
  try {
    const response = await fetch("/api/admin/session", {
      headers: {
        Accept: "application/json",
      },
    });

    if (response.status === 401) {
      showDisconnectedState();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to load the admin session");
    }

    const data = await response.json();
    showConnectedState(data);
    await loadOverlayAccessStatus();
  } catch {
    showErrorState();
  }
}

loadAdminSession();
