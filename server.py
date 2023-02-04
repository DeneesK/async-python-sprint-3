import re
import json
import asyncio
from asyncio.streams import StreamReader, StreamWriter

from logger_ import logging
from config import settings
from models import ServersClientModel, Request, Response, MessageModel


logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host: str = settings.server_host,
                 port: int = settings.port,
                 msg_limit: int = settings.buffer_size) -> None:
        self.host = host
        self.port = port
        self.msg_buffer_limit = msg_limit
        self.msg_id = 0
        self.msg_buffer = []
        self.connected_clients = {}
        self.disconnected_clients = {}
        self.private_message = {}
        self.routes = {
            '/connect': self.connect,
            '/send': self.send,
            '/sendto': self.send_to,
            '/getupdate': self.get_update,
            '/status': self.get_status,
            '/close': self.close,
        }

    def add_message_to_buffer(self, message: MessageModel) -> None:
        if len(self.msg_buffer) >= self.msg_buffer_limit:
            self.msg_buffer.pop()
        self.msg_buffer.append(message)

    async def parse_request(self, reader: StreamReader) -> Request:
        try:
            head = await reader.readuntil(separator=b'\r\n\r\n')
        except Exception as ex:
            logger.error(ex)
        raw = re.findall(b'\w*\s/\w*\s\w*/\d.\d', head)  # noqa: W605
        method, path, *_ = raw[0].decode().split(' ')
        if method.upper() == 'GET':
            return Request(method=method, path=path)
        try:
            body = await reader.readuntil(separator=b'}')
        except Exception as ex:
            logger.error(ex)
        return Request(method=method, path=path, body=body)

    async def on_connect_get_updates(self, client: ServersClientModel) -> str:
        """Send unreceived messages to user with a new connection of an existing user"""
        text = ''
        for msg in self.msg_buffer:
            if msg.msg_id > client.last_got_msg_id:
                text += msg.msg + '\n'
                client.last_got_msg_id = msg.msg_id
        if private_messages := self.private_message.get(client.name):
            for msg in private_messages:
                text += msg + '\n'
            del self.private_message[client.name]
        return text

    async def on_first_connect_get_last_messages(self, client: ServersClientModel) -> str:
        """Send all messages from buffer for new user and mark last sent message id to user"""
        text = ''
        for msg in self.msg_buffer:
            text += msg.msg + '\n'
            client.last_got_msg_id = msg.msg_id
        return text

    async def connect(self, request: Request) -> Response:
        """
        If the user has previously connected, it gets it from disconnected_clients,
        if the user for the first time then creates a new ServerClientModel for it and places
        it in connected_clients.
        """
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        try:
            client = ServersClientModel.parse_obj(json.loads(request.body))
        except Exception as ex:
            logger.error(ex)
        if clt := self.disconnected_clients.get(client.id):
            logger.info(f'User {client.id} already exists')
            self.connected_clients[clt.id] = clt
            del self.disconnected_clients[client.id]
            text = await self.on_connect_get_updates(clt)
            return Response(text=text)
        logger.info(f'New user: {client.id} connected')
        self.connected_clients[client.id] = client
        text = await self.on_first_connect_get_last_messages(client)
        return Response(text=text)

    async def close(self, request: Request) -> Response:
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        clnt = json.loads(request.body)
        client = self.connected_clients[clnt['id']]
        self.disconnected_clients[client.id] = client
        del self.connected_clients[client.id]
        return Response()

    async def get_status(self, request: Request) -> Response:
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        text = f'Server status: OK. {len(self.connected_clients)} user(s) are(is) connected to server'
        return Response(text=text)

    async def send_private_message(self, client_name: str):
        if messages := self.private_message.get(client_name):
            return messages.pop()
        return None

    async def get_update(self, request: Request) -> Response:
        """Send last unreceived messages and marks last send message id for user"""
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        clnt = json.loads(request.body)
        client = self.connected_clients[clnt['id']]
        if msg := await self.send_private_message(client.name):
            return Response(text=msg)
        for msg in self.msg_buffer:
            if msg.msg_id > client.last_got_msg_id:
                client.last_got_msg_id = msg.msg_id
                return Response(text=msg.msg)
        return Response()

    async def send(self, request: Request) -> Response:
        """Get messages from users for all users"""
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        try:
            message = MessageModel.parse_obj(json.loads(request.body))
        except Exception as ex:
            logger.error(ex)
        self.msg_id += 1
        message.msg_id = self.msg_id
        self.add_message_to_buffer(message)
        return Response()

    async def send_to(self, request: Request) -> Response:
        """Get messages from users to certain user"""
        logger.info(f'{request.method} {self.host}:{self.port}{request.path}')
        try:
            message_model = MessageModel.parse_obj(json.loads(request.body))
        except Exception as ex:
            logger.error(ex)
        msg = f'***{message_model.name}***: {message_model.msg}'
        if not self.private_message.get(message_model.to_user):
            self.private_message[message_model.to_user] = [msg]
        else:
            self.private_message[message_model.to_user].append(msg)
        return Response()

    async def on_request(self, reader: StreamReader, writer: StreamWriter):
        request = await self.parse_request(reader)
        coro = self.routes.get(request.path)
        r = await coro(request)
        resonse = r.create_response()
        try:
            writer.write(resonse)
            writer.close()
        except Exception as ex:
            logger.error(ex)

    async def run(self):
        srv = await asyncio.start_server(self.on_request, self.host, self.port)
        async with srv:
            logger.info(f'Server started at {self.host}:{self.port}')
            await srv.serve_forever()


if __name__ == '__main__':
    server = Server()
    asyncio.run(server.run())
