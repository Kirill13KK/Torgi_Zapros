from contextlib import contextmanager
from pathlib import Path
import portalocker


class RunnerBusyError(RuntimeError):
    pass


@contextmanager
def acquire_runner_lock(lock_path: str):
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    try:
        portalocker.lock(fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.exceptions.LockException as e:
        fh.close()
        raise RunnerBusyError("runner already running") from e
    try:
        yield
    finally:
        portalocker.unlock(fh)
        fh.close()
