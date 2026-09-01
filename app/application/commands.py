from dataclasses import dataclass

from app.application.service import GiveawayService
from app.domain.giveaway import Participant


@dataclass(frozen=True)
class ChatUser:
    twitch_user_id: str
    login: str
    display_name: str


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    message: str


class GiveawayCommandHandler:
    def __init__(
        self,
        service: GiveawayService,
        broadcaster_id: str,
        prefix: str = "!",
    ) -> None:
        if not broadcaster_id.strip():
            raise ValueError("The broadcaster ID cannot be empty")

        if not prefix:
            raise ValueError("The command prefix cannot be empty")

        self._service: GiveawayService = service
        self._broadcaster_id: str = broadcaster_id
        self._prefix: str = prefix

    async def handle(
        self,
        content: str,
        author: ChatUser,
    ) -> CommandResult | None:
        parsed_command = self._parse(content)
        if parsed_command is None:
            return None

        command, argument = parsed_command
        management_commands = {"lot", "start", "pull", "stop"}

        if (
            command in management_commands
            and author.twitch_user_id != self._broadcaster_id
        ):
            return CommandResult(False, "This command is reserved for the broadcaster")

        if command != "lot" and argument:
            return CommandResult(False, f"{self._prefix}{command} takes no argument")

        try:
            return await self._execute(command, argument, author)
        except (RuntimeError, ValueError) as error:
            return CommandResult(False, str(error))

    def _parse(self, content: str) -> tuple[str, str] | None:
        normalized_content = content.strip()
        if not normalized_content.startswith(self._prefix):
            return None

        command_text, _, argument = normalized_content.partition(" ")
        command = command_text.removeprefix(self._prefix).casefold()

        if command not in {"lot", "start", "join", "pull", "stop"}:
            return None

        return command, argument.strip()

    async def _execute(
        self,
        command: str,
        argument: str,
        author: ChatUser,
    ) -> CommandResult:
        match command:
            case "lot":
                await self._service.set_lot(argument)
                return CommandResult(True, "The giveaway is waiting")
            case "start":
                await self._service.start()
                return CommandResult(True, "The giveaway is open")
            case "join":
                was_added = await self._service.join(
                    Participant(
                        twitch_user_id=author.twitch_user_id,
                        login=author.login,
                        display_name=author.display_name,
                    )
                )
                if not was_added:
                    return CommandResult(False, "The viewer is already registered")

                return CommandResult(True, "The viewer is registered")
            case "pull":
                winner = await self._service.pull()
                return CommandResult(True, f"The winner is {winner.display_name}")
            case "stop":
                await self._service.stop()
                return CommandResult(True, "The giveaway is hidden")
            case _:
                raise RuntimeError("Unsupported giveaway command")
