import asyncio
import os
import signal

from sys import argv

from multidict import CIMultiDict  # type: ignore


OS_IS_WINDOWS = os.name == "nt"


class Header(CIMultiDict):
    def get_all(self, key):
        return self.getall(key, default=[])


use_trio = argv[0].endswith("hypercorn") and "trio" in argv

if use_trio:  # pragma: no cover
    import trio  # type: ignore

    def stat_async(path):
        return trio.Path(path).stat()

    open_async = trio.open_file
    CancelledErrors = tuple([asyncio.CancelledError, trio.Cancelled])
else:
    from aiofiles import open as aio_open  # type: ignore
    from aiofiles.os import stat as stat_async  # type: ignore  # noqa: F401

    async def open_async(file, mode="r", **kwargs):
        return aio_open(file, mode, **kwargs)

    CancelledErrors = tuple([asyncio.CancelledError])


def ctrlc_workaround_for_windows(app):
    async def stay_active(app):
        """Asyncio wakeups to allow receiving SIGINT in Python"""
        while not die:
            # If someone else stopped the app, just exit
            if app.is_stopping:
                return
            # Windows Python blocks signal handlers while the event loop is
            # waiting for I/O. Frequent wakeups keep interrupts flowing.
            await asyncio.sleep(0.1)
        # Can't be called from signal handler, so call it from here
        app.stop()

    def ctrlc_handler(sig, frame):
        nonlocal die
        if die:
            raise KeyboardInterrupt("Non-graceful Ctrl+C")
        die = True

    die = False
    signal.signal(signal.SIGINT, ctrlc_handler)
    app.add_task(stay_active)
