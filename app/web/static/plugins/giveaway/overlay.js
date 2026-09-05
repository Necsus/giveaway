const giveawayElement = document.querySelector("#giveaway");
const lotElement = document.querySelector("#lot");
const statusElement = document.querySelector("#status");
const participantsElement = document.querySelector("#participants");
const winnerElement = document.querySelector("#winner");

function renderGiveaway(state) {
  giveawayElement.hidden = state.state === "HIDDEN";
  lotElement.textContent = state.lot ?? "";
  statusElement.textContent = state.state;
  participantsElement.textContent = String(state.participant_count);

  const winners = state.winners ?? [];
  winnerElement.textContent = winners
    .map((winner, index) => `${index + 1}. ${winner.display_name}`)
    .join(" • ");
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = window.location.hash.slice(1);

  if (!token) {
    return;
  }

  const websocket = new WebSocket(
    `${protocol}//${window.location.host}/plugins/giveaway/ws`,
  );

  websocket.addEventListener("open", () => {
    websocket.send(JSON.stringify({
      type: "overlay.authenticate",
      token,
    }));
  });

  websocket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "giveaway.state") {
      renderGiveaway(message.data);
    }
  });

  websocket.addEventListener("close", (event) => {
    if (event.code === 1008) {
      clearGiveaway();
      return;
    }
    window.setTimeout(connectWebSocket, 1000);
  });

  websocket.addEventListener("error", () => {
    websocket.close();
  });
}

function clearGiveaway() {
  giveawayElement.hidden = true;
  lotElement.textContent = "";
  statusElement.textContent = "";
  participantsElement.textContent = "0";
  winnerElement.textContent = "";
}

connectWebSocket();
