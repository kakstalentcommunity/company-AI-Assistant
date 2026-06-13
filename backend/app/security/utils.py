from fastapi import Request


MAX_FIELD_LENGTH = 255


def truncate(value: str | None, limit: int = MAX_FIELD_LENGTH) -> str:
    if not value:
        return ""
    return value[:limit]


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return truncate(forwarded.split(",", 1)[0].strip(), 100)

    if request.client:
        return truncate(request.client.host, 100)

    return "unknown"


def get_user_agent(request: Request) -> str:
    return truncate(request.headers.get("user-agent", ""), MAX_FIELD_LENGTH)


def get_request_target(request: Request) -> str:
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    return truncate(path, 1_000)
