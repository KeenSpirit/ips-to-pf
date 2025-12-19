import logging.config
import powerfactory as pf  # noqa
from pathlib import Path


"""
logging aims:
Store log file on network drive
Log user calls for script improvement
Must handle multiple simultaneous file writes

What information needs to be logged?
- list of relevant devices found in IPS, script failure exception, data_capture_list, updates,

"""



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


import logging
import logging.handlers
import os
import sys
import threading
import queue
import atexit


class QueueLogger:
    """
    A logger that uses a queue and separate thread for writing to avoid blocking
    """

    def __init__(self, log_file, max_bytes=10 * 1024 * 1024, backup_count=5):
        self.log_file = log_file
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()

        # Setup file handler
        self.file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            delay=True
        )

        # Setup formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - PID:%(process)d - User:%(username)s - %(message)s'
        )
        self.file_handler.setFormatter(formatter)

        # Setup queue handler
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)

        # Start the logging thread
        self.logging_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.logging_thread.start()

        # Register cleanup
        atexit.register(self.stop)

    def _log_worker(self):
        """Background thread that processes log messages"""
        while not self.stop_event.is_set():
            try:
                # Get log record from queue (timeout to check stop event)
                record = self.log_queue.get(timeout=1)
                if record is None:  # Poison pill
                    break

                # Add username to record
                record.username = os.getenv('USERNAME', os.getenv('USER', 'unknown'))

                # Write to file
                self.file_handler.emit(record)

            except queue.Empty:
                continue
            except Exception as e:
                # Handle errors in logging (avoid infinite recursion)
                sys.stderr.write(f"Logging error: {e}\n")

    def get_logger(self, name=None):
        """Get a logger configured to use the queue"""
        logger = logging.getLogger(name or __name__)
        logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        logger.addHandler(self.queue_handler)
        logger.propagate = False

        return logger

    def stop(self):
        """Stop the logging thread gracefully"""
        if not self.stop_event.is_set():
            self.stop_event.set()
            self.log_queue.put(None)  # Poison pill
            if self.logging_thread.is_alive():
                self.logging_thread.join(timeout=5)


# Global logger instance
_queue_logger = None


def setup_concurrent_logging():
    """Setup the concurrent logging system"""
    global _queue_logger

    if _queue_logger is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(script_dir, 'application.log')
        _queue_logger = QueueLogger(log_file)

    return _queue_logger.get_logger()


# Usage example
if __name__ == "__main__":
    logger = setup_concurrent_logging()

    logger.info("Script started")

    # Simulate concurrent work
    import time

    for i in range(10):
        logger.info(f"Processing item {i + 1}")
        logger.debug(f"Debug info for item {i + 1}")
        time.sleep(0.5)

    logger.info("Script completed")

    # Cleanup happens automatically via atexit


def log_device_atts(prot_dev):
    """
    Log the device attributes.
    Settings attribute is logged as 'yes/no' to keep logged data to manageable levels
    Args:
        prot_dev:

    Returns:
    logged device attributes
    """

    logging.info(f"Attributes for protection device{prot_dev.device}:")
    attributes = dir(prot_dev)
    for attr in attributes:
        if not attr.startswith('__'):
            value = getattr(prot_dev, attr)
            if attr == 'settings':
                if len(value) > 0:
                    value = 'settings loaded'
                else:
                    value = 'no settings loaded'
            logging.info(f"{attr}: {value}")

