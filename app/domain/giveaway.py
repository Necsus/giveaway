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
        self.winners: list[Participant] = []

    def restore(
        self,
        giveaway_id: str,
        lot: str,
        state: GiveawayState,
        participants: list[Participant],
        winner_user_ids: list[str],
    ) -> None:
        if self.state is not GiveawayState.HIDDEN:
            raise RuntimeError("The giveaway engine is already active")

        if state is GiveawayState.HIDDEN:
            raise ValueError("A hidden giveaway cannot be restored")

        participant_by_id = {
            participant.twitch_user_id: participant for participant in participants
        }

        if len(participant_by_id) != len(participants):
            raise RuntimeError("The restored participants contain duplicates")

        if len(set(winner_user_ids)) != len(winner_user_ids):
            raise RuntimeError("The restored winners contain duplicates")

        try:
            winners = [
                participant_by_id[winner_user_id] for winner_user_id in winner_user_ids
            ]
        except KeyError as error:
            raise RuntimeError("A restored winner is not a participant") from error

        if state is GiveawayState.WINNER and not winners:
            raise RuntimeError("A drawn giveaway must have at least one winner")

        if state is not GiveawayState.WINNER and winners:
            raise RuntimeError("A giveaway without a draw cannot have winners")

        self.state = state
        self.giveaway_id = giveaway_id
        self.lot = lot
        self.participants = participants.copy()
        self.winners = winners

    def set_lot(self, lot: str) -> None:
        if self.state is not GiveawayState.HIDDEN:
            raise RuntimeError("A giveaway is already active")

        cleaned_lot = lot.strip()

        if not cleaned_lot:
            raise ValueError("The lot name cannot be empty")

        self.giveaway_id = str(uuid4())
        self.lot = cleaned_lot
        self.participants.clear()
        self.winners.clear()
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
        if self.state not in {GiveawayState.OPEN, GiveawayState.WINNER}:
            raise RuntimeError("The giveaway is not open")

        if not self.participants:
            raise RuntimeError("The giveaway has no participants")

        winner_ids = {winner.twitch_user_id for winner in self.winners}

        eligible_participants = [
            participant
            for participant in self.participants
            if participant.twitch_user_id not in winner_ids
        ]

        if not eligible_participants:
            raise RuntimeError("All participants have already won")

        winner = choice(eligible_participants)
        self.winners.append(winner)
        self.state = GiveawayState.WINNER

        return winner

    def stop(self) -> None:
        if self.state is GiveawayState.HIDDEN:
            raise RuntimeError("There is no active giveaway")

        self.state = GiveawayState.HIDDEN
        self.giveaway_id = None
        self.lot = None
        self.participants.clear()
        self.winners.clear()

    def snapshot(self) -> dict[str, object]:
        winners = [
            {
                "twitch_user_id": winner.twitch_user_id,
                "display_name": winner.display_name,
            }
            for winner in self.winners
        ]

        return {
            "state": self.state.value,
            "giveaway_id": self.giveaway_id,
            "lot": self.lot,
            "participant_count": len(self.participants),
            "participants": [
                participant.display_name for participant in self.participants
            ],
            "winners": winners,
        }
