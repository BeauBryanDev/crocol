class CrocolError(Exception):
    """Base error with an HTTP status and a fixed, user-safe message."""

    status_code = 500
    public_message = "internal error"

    def __init__(self, message: str | None = None) -> None:

        super().__init__(message or self.public_message)
        self.public_message = message or self.public_message


class ImageError(CrocolError, ValueError):
    status_code = 400
    public_message = "the image could not be processed"


class InvalidImageError(ImageError):
    status_code = 400
    public_message = "the file is not a readable image"


class UnsupportedImageFormatError(ImageError):
    status_code = 415
    public_message = "unsupported image format; use JPEG, PNG or WebP"


class ImageTooLargeError(ImageError):
    status_code = 413
    public_message = "the image is too large (max 10 MB and 24 megapixels)"


class QuestionError(CrocolError, ValueError):
    status_code = 422
    public_message = "the question must have between 3 and 2000 characters"


class RateLimitedError(CrocolError):
    status_code = 429
    public_message = "too many questions; please wait before asking again"

    def __init__(self, retry_after: int, message: str | None = None) -> None:

        super().__init__(message)
        self.retry_after = retry_after


class BusyError(CrocolError):
    status_code = 429
    public_message = "Crocol is busy answering other questions; try again"


class BudgetExceededError(CrocolError):
    status_code = 503
    public_message = "the daily demo budget is used up; try again tomorrow"


class NotFoundError(CrocolError):

    status_code = 404
    public_message = "not found"


class UnavailableError(CrocolError):

    status_code = 503
    public_message = "this feature is not available right now"
