import asyncio
from urllib.parse import urlparse, parse_qsl
from asyncio import Event, FIRST_COMPLETED
import signal
import typing
from logging import getLogger, DEBUG


stop = Event()
loop = asyncio.get_event_loop()
lg = getLogger(__name__)
lg.setLevel(DEBUG)


def make_handler(get_ans: typing.Callable[[dict], str]):

    async def handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        data = await reader.read(200)
        print(data)
        message = data.decode()
        addr = writer.get_extra_info('peername')
        lg.debug('process msg "%s" from %s', message, addr)
        try:
            (_, p, *_) = message.split(' ')
            p = dict(parse_qsl(urlparse(p).query))
            lg.debug('query %s', p)
            ans = get_ans(p)
            ans = f'''HTTP/1.1 200 OK\nContent-Length: {len(ans)}\n\n{ans}'''.encode()  # \nContent-Length: 6
            ans = b'HTTP/1.1 200 OK\r\n\r\n7:2'
            print(ans)
        except Exception as exc:
            print(exc)
            lg.exception('process msg "%s" from %s', message, addr)
            ans = '''HTTP/1.1 500\n\n'''.encode()
        writer.write(ans)
        await writer.drain()
        # writer.transport.close()
        writer.close()
        await writer.wait_closed()
    return handler


async def serve():
    server = await asyncio.start_server(
        make_handler(lambda x: '7:2'),
        host='0.0.0.0',
        port=1111,
    )
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')
    async with server:
        await asyncio.wait((server.serve_forever(), stop.wait()), return_when=FIRST_COMPLETED)

if __name__ == '__main__':
    loop.add_signal_handler(
        signal.SIGINT, stop.set
    )
    loop.run_until_complete(serve())