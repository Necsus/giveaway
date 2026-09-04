import logging

from typing_extensions import override

OAUTH_CALLBACK_PATH = "/auth/twitch/callback"
REDACTED_OAUTH_CALLBACK = f"{OAUTH_CALLBACK_PATH}?<redacted>"


class OAuthCallbackAccessFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args
        if not isinstance(arguments, tuple) or len(arguments) < 3:
            return True

        request_path = arguments[2]
        if not isinstance(request_path, str):
            return True

        if not request_path.startswith(f"{OAUTH_CALLBACK_PATH}?"):
            return True

        redacted_arguments = list(arguments)
        redacted_arguments[2] = REDACTED_OAUTH_CALLBACK
        record.args = tuple(redacted_arguments)
        return True


def install_oauth_access_log_filter() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    if any(
        isinstance(current_filter, OAuthCallbackAccessFilter)
        for current_filter in access_logger.filters
    ):
        return

    access_logger.addFilter(OAuthCallbackAccessFilter())
