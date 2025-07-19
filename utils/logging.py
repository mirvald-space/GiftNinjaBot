# --- Standard libraries ---
import logging

def setup_logging(level=logging.INFO):
    """
    Initialization of standard logging for the project.

    Arguments:
        level (int, optional): Logging level (default is logging.INFO).
    """
    logging.basicConfig(
        level=level,
        format="[{asctime}] [{levelname}] {name}: {message}",
        style="{",
        datefmt="%d.%m.%Y %H:%M:%S"
    )
