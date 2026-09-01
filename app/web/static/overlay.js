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
  winnerElement.textContent = state.winner?.display_name ?? "";
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const websocket = new WebSocket(
    `${protocol}//${window.location.host}/ws/overlay`,
  );

  websocket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "giveaway.state") {
      renderGiveaway(message.data);
    }
  });

  websocket.addEventListener("close", () => {
    window.setTimeout(connectWebSocket, 1000);
  });

  websocket.addEventListener("error", () => {
    websocket.close();
  });
}

connectWebSocket();
