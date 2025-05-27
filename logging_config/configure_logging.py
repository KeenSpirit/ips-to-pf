import logging
import logging.config
import powerfactory as pf  # noqa
from pathlib import Path


def getpath(subdir="IPStoPFlog"):
    """Returns a path for the PowerFactory results. The path will try and
    resolve the path when using citrix. When not conneting via citrix, the path
    will use the user folder on the local machine
    """
    user = Path.home().name
    basepath = Path("//client/c$/Users") / user
    if basepath.exists():
        clientpath = basepath / subdir
    else:
        clientpath = Path("c:/Users") / user / subdir
    clientpath.mkdir(exist_ok=True)

    return clientpath


def log_arguments(func):
    def wrapper(*args, **kwargs):
        # Log the function name and its arguments
        arg_str = ', '.join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
        logging.info(f"Function {func.__name__} called with arguments: {arg_str}")
        return func(*args, **kwargs)
    return wrapper
