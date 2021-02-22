import asyncio
from asyncio import Event, FIRST_COMPLETED
import signal


stop = Event()
loop = asyncio.get_event_loop()


async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
):
    await reader.read(100)
    ans = b'HTTP/1.1 200 OK\r\nContent-Length:1\r\n\r\nd'
    writer.write(ans)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def serve():
    server = await asyncio.start_server(
        handler,
        host='0.0.0.0',
        port=8888,
    )
    async with server:
        await asyncio.wait((server.serve_forever(), stop.wait()), return_when=FIRST_COMPLETED)

if __name__ == '__main__':
    loop.add_signal_handler(
        signal.SIGINT, stop.set
    )
    loop.run_until_complete(serve())
