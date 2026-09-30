class SOSContadorError(Exception):
    """Base error for the SOS Contador connector."""


class AuthenticationError(SOSContadorError):
    """Login or CUIT-token exchange failed."""


class APIError(SOSContadorError):
    """The API returned a non-2xx response."""

    def __init__(self, status_code: int, message: str, payload=None):
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.payload = payload
