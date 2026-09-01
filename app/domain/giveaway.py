from dataclasses import dataclass
from enum import StrEnum
from secrets import choice
from uuid import uuid4


class GiveawayState(StrEnum):
    HIDDEN = "HIDDEN"
    WAITING = "WAITING"
    OPEN = "OPEN"
    WINNER = "WINNER"


@dataclass(frozen=True)
class Participant:
    twitch_user_id: str
    login: str
    display_name: str


class GiveawayEngine:
    def __init__(self) -> None:
        self.state: GiveawayState = GiveawayState.HIDDEN
        self.giveaway_id: str | None = None
        self.lot: str | None = None
        self.participants: list[Participant] = []
        self.winner: Participant | None = None

    def restore(
        self,
        giveaway_id: str,
        lot: str,
        state: GiveawayState,
        participants: list[Participant],
        winner_user_id: str | None,
    ) -> None:
        if self.state is not GiveawayState.HIDDEN:
            raise RuntimeError("The giveaway engine is already active")

        if state is GiveawayState.HIDDEN:
            raise ValueError("A hidden giveaway cannot be restored")

        winner = next(
            (
                participant
                for participant in participants
                if participant.twitch_user_id == winner_user_id
            ),
            None,
        )

        if state is GiveawayState.WINNER and winner is None:
            raise RuntimeError("The restored winner is not a participant")

        if state is not GiveawayState.WINNER and winner_user_id is not None:
            raise RuntimeError("A giveaway without a draw cannot have a winner")

        self.state = state
        self.giveaway_id = giveaway_id
        self.lot = lot
        self.participants = participants.copy()
        self.winner = winner

    def set_lot(self, lot: str) -> None:
        if self.state is not GiveawayState.HIDDEN:
            raise RuntimeError("A giveaway is already active")

        cleaned_lot = lot.strip()

        if not cleaned_lot:
            raise ValueError("The lot name cannot be empty")

        self.giveaway_id = str(uuid4())
        self.lot = cleaned_lot
        self.participants.clear()
        self.winner = None
        self.state = GiveawayState.WAITING

    def start(self) -> None:
        if self.state is not GiveawayState.WAITING:
            raise RuntimeError("A giveaway is not waiting")

        self.state = GiveawayState.OPEN

    def join(self, participant: Participant) -> bool:
        if self.state is not GiveawayState.OPEN:
            raise RuntimeError("The giveaway is not open")

        for registered_participant in self.participants:
            if registered_participant.twitch_user_id == participant.twitch_user_id:
                return False

        self.participants.append(participant)
        return True

    def pull(self) -> Participant:
        if self.state is not GiveawayState.OPEN:
            raise RuntimeError("The giveaway is not open")

        if not self.participants:
            raise RuntimeError("The giveaway has no participants")

        winner = choice(self.participants)

        self.winner = winner
        self.state = GiveawayState.WINNER

        return winner

    def stop(self) -> None:
        if self.state is GiveawayState.HIDDEN:
            raise RuntimeError("There is no active giveaway")

        self.state = GiveawayState.HIDDEN
        self.giveaway_id = None
        self.lot = None
        self.participants.clear()
        self.winner = None

    def snapshot(self) -> dict[str, object]:
        winner: dict[str, str] | None = None

        if self.winner is not None:
            winner = {
                "twitch_user_id": self.winner.twitch_user_id,
                "display_name": self.winner.display_name,
            }

        return {
            "state": self.state.value,
            "giveaway_id": self.giveaway_id,
            "lot": self.lot,
            "participant_count": len(self.participants),
            "participants": [
                participant.display_name for participant in self.participants
            ],
            "winner": winner,
        }
