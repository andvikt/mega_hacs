import asyncio
import itertools
from heapq import heappush
from contextlib import asynccontextmanager


_params = ['m', 'click', 'cnt', 'pt']


def make_ints(d: dict):
    for x in _params:
        try:
            d[x] = int(d.get(x, 0))
        except (ValueError, TypeError):
            pass
    if 'm' not in d:
        d['m'] = 0
    if 'click' not in d:
        d['click'] = 0


def int_ignore(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return x


class PriorityLock(asyncio.Lock):
    """
    You can acquire lock with some kind of priority in mind, so that locks with higher priority will be released first.
    priority can be set with lck.acquire(1)
    or by using context manager:
    >>> lck = PriorityLock()
    ... async with lck(1):
    ...     # do something
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cnt = itertools.count()

    def __call__(self, priority=0):
        return self._with_priority(priority)

    @asynccontextmanager
    async def _with_priority(self, p):
        await self.acquire(p)
        try:
            yield
        finally:
            self.release()

    @property
    def _loop(self):
        return asyncio.get_event_loop()

    async def acquire(self, priority=0) -> bool:
        """Acquire a lock.

                This method blocks until the lock is unlocked, then sets it to
                locked and returns True.
                """
        if (not self._locked and (self._waiters is None or
                                  all(w.cancelled() for _, _, w in self._waiters))):
            self._locked = True
            return True

        if self._waiters is None:
            self._waiters = []

        fut = self._loop.create_future()
        cnt = next(self._cnt)
        heappush(self._waiters, (priority, cnt, fut))

        # Finally block should be called before the CancelledError
        # handling as we don't want CancelledError to call
        # _wake_up_first() and attempt to wake up itself.
        try:
            try:
                await fut
            finally:
                self._waiters.remove((priority, cnt, fut))
        except asyncio.exceptions.CancelledError:
            if not self._locked:
                self._wake_up_first()
            raise

        self._locked = True
        return True

    def release(self):
        """Release a lock.

        When the lock is locked, reset it to unlocked, and return.
        If any other coroutines are blocked waiting for the lock to become
        unlocked, allow exactly one of them to proceed.

        When invoked on an unlocked lock, a RuntimeError is raised.

        There is no return value.
        """
        if self._locked:
            self._locked = False
            self._wake_up_first()
        else:
            raise RuntimeError('Lock is not acquired.')

    def _wake_up_first(self):
        """Wake up the first waiter if it isn't done."""
        if not self._waiters:
            return
        try:
            _, _, fut = self._waiters[0]
        except IndexError:
            return

        # .done() necessarily means that a waiter will wake up later on and
        # either take the lock, or, if it was cancelled and lock wasn't
        # taken already, will hit this again and wake up a new waiter.
        if not fut.done():
            fut.set_result(True)


def map_reorder_rgb(rgb: list, from_: str, to_: str):
    if from_ == to_:
        return rgb
    mapping = [from_.index(x) for x in to_]
    return [rgb[x] for x in mapping]
