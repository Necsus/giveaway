const disconnectedState = document.querySelector("#disconnected-state");
const connectedState = document.querySelector("#connected-state");
const adminError = document.querySelector("#admin-error");
const streamerAvatar = document.querySelector("#streamer-avatar");
const streamerDisplayName = document.querySelector("#streamer-display-name");
const streamerLogin = document.querySelector("#streamer-login");
const activeStreamer = document.querySelector("#active-streamer");
const botLogin = document.querySelector("#bot-login");
const sessionStatus = document.querySelector("#session-status");
const chatStatus = document.querySelector("#chat-status");
const overlayUrlInput = document.querySelector("#overlay-url");
const copyOverlayUrlButton = document.querySelector("#copy-overlay-url");
const copyStatus = document.querySelector("#copy-status");
const logoutButton = document.querySelector("#logout-button");
const logoutStatus = document.querySelector("#logout-status");

const chatStatusLabels = {
  ready: "Opérationnel",
  degraded: "Dégradé",
  disabled: "Désactivé",
};
const overlayUrl = new URL(
  "/overlay",
  window.location.origin,
).href;
overlayUrlInput.value = overlayUrl;

copyOverlayUrlButton.addEventListener("click", async () => {
  copyStatus.textContent = "";

  try {
    await navigator.clipboard.writeText(overlayUrlInput.value);
    copyStatus.textContent = "URL copiée.";
  } catch {
    overlayUrlInput.focus();
    overlayUrlInput.select();
    copyStatus.textContent = "Copie impossible. L'URL a été sélectionnée pour une copie manuelle.";
  }
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
  disconnectedState.hidden = false;
  connectedState.hidden = true;
  adminError.hidden = true;
}

function showErrorState() {
  disconnectedState.hidden = true;
  connectedState.hidden = true;
  adminError.hidden = false;
}

function showConnectedState(data) {
  const session = data.session;

  streamerDisplayName.textContent = session.display_name;
  streamerLogin.textContent = `@${session.login}`;
  sessionStatus.textContent = "Connectée";
  chatStatus.textContent = chatStatusLabels[data.chat.status] ?? "Inconnu";

  if (session.profile_image_url) {
    streamerAvatar.src = session.profile_image_url;
    streamerAvatar.alt = `Avatar Twitch de ${session.display_name}`;
    streamerAvatar.hidden = false;
  } else {
    streamerAvatar.removeAttribute("src");
    streamerAvatar.alt = "";
    streamerAvatar.hidden = true;
  }

  if (data.active_streamer === null) {
    activeStreamer.textContent = "Aucun streamer actif";
  } else {
    activeStreamer.textContent =
      `${data.active_streamer.display_name} ` +
      `(@${data.active_streamer.login})`;
  }

  botLogin.textContent = `@${data.bot.login}`;

  disconnectedState.hidden = true;
  connectedState.hidden = false;
  adminError.hidden = true;
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
  } catch {
    showErrorState();
  }
}

loadAdminSession();
