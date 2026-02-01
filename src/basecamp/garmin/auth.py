import garth

from basecamp.config import GARTH_HOME


def login() -> None:
    """Prompt for Garmin credentials, authenticate, and save session."""
    email = input("Garmin email: ")
    password = input("Garmin password: ")
    garth.login(email, password)
    garth.save(str(GARTH_HOME))


def get_client():
    """Resume saved garth session and return the garth module ready for API calls."""
    garth.resume(str(GARTH_HOME))
    return garth
