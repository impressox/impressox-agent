import asyncio

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, run normally (e.g. in CLI, test)
        return asyncio.run(coro)
    
    # Already inside a running loop → run coroutine in thread-safe manner
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
