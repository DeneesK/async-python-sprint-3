import os
import re
import time
import logging

from aiohttp_swagger import setup_swagger, swagger_path
from aiohttp import web
from aiohttp.web import Response, Application, Request

from config import LOGGER_SETTINGS, BUFFER_SIZE, MSG_LIMIT, LIMIT_UPDATE_PERIOD, TITLE
from models import MessageModel, ServersClientModel


logging.basicConfig(**LOGGER_SETTINGS)
logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host="127.0.0.1", port=8000, app: Application = Application(), server: web = web) -> None:
        self.host = host
        self.port = port
        self.app = app
        self.server = server
        self.connected_clients = []
        self.messages_bufer = []
        self.msg_id = 0
        self.client_id_of_last_received_msg = {}
        self.msg_to_user = {}
        self.sent_files_to_user = {}
        self.files = []

    @swagger_path('swagger_docs/get_status.yaml')
    async def send_status(self, request: Request) -> Response:
        number = len(self.connected_clients)
        return Response(text=f'Status: OK. There is/are {number} user/s in the chat')

    @swagger_path('swagger_docs/connect.yaml')
    async def connect(self, request: Request) -> Response:
        client = ServersClientModel.parse_obj(await request.json())
        self.connected_clients.append(client)
        return Response(text='Connected')

    @swagger_path('swagger_docs/get_message.yaml')
    async def get_message(self, request: Request) -> Response:
        msg = MessageModel.parse_obj(await request.json())
        client = [c for c in self.connected_clients if c.id == msg.id]
        self.set_msg_over_limit_status(client[0])
        if not client[0].over_limit:
            client[0].sent_messages += 1
            self.msg_id += 1
            msg.msg_id = self.msg_id
            self.add_to_msg_buffer(msg)
            return Response()
        return Response(text='!!!Server: Exceeded messages limit. Wait hour')

    @swagger_path('swagger_docs/get_message_to_user.yaml')
    async def get_message_to_user(self, request: Request) -> Response:
        msg = MessageModel.parse_obj(await request.json())
        client = [c for c in self.connected_clients if c.id == msg.id]
        self.set_msg_over_limit_status(client[0])
        if not client[0].over_limit:
            client[0].sent_messages += 1
            to_user = msg.to_user
            self.msg_to_user[to_user] = f'***{msg.name}***: {msg.msg}'
            return Response()
        return Response(text='!!!Server: Exceeded messages limit. Wait hour')

    @swagger_path('swagger_docs/send_messages_from_buffer.yaml')
    async def send_messages_to_users_from_buffer(self, request: Request) -> Response:
        client = ServersClientModel.parse_obj(await request.json())
        if client not in self.connected_clients:
            if self.messages_bufer:
                text = ''
                for msg in self.messages_bufer[:-1]:
                    text += f'{msg.name}: {msg.msg}\n'
                last = self.messages_bufer[-1]
                text += f'{last.name}: {last.msg}'
                self.client_id_of_last_received_msg[client.id] = last.msg_id
                return Response(text=text)
        return Response()

    @swagger_path('swagger_docs/send_update.yaml')
    async def send_update(self, request: Request) -> Response:
        client = ServersClientModel.parse_obj(await request.json())
        if self.msg_to_user.get(client.name, None):
            msg = self.msg_to_user.get(client.name)
            del self.msg_to_user[client.name]
            return Response(text=msg)
        last_send_msg_id = self.client_id_of_last_received_msg.get(client.id, 0)
        for m in self.messages_bufer:
            if m.msg_id > last_send_msg_id:
                self.client_id_of_last_received_msg[client.id] = m.msg_id
                return Response(text=f'{m.name}: {m.msg}')
        return Response()

    @swagger_path('swagger_docs/close_connect.yaml')
    async def del_client_from_connected_list(self, request: Request) -> Response:
        client = ServersClientModel.parse_obj(await request.json())
        self.connected_clients.remove(client)
        return Response()

    async def prepare_data_for_saving_file(self, data: bytes) -> dict:
        """Return the filename and file format"""
        file_bytes = re.findall(b'\\r\\n\\r\\n.*', data, flags=re.S)
        file_bytes = file_bytes[0].strip()
        file_info = re.findall(b'\w*%20\w*-\w*-\w*-\w*-\w*%20\w*', data)  # noqa: W605
        file_info = file_info[0].decode()
        user_name, user_id, file_format = file_info.split('%20')
        return {'file': file_bytes, 'name': user_name, 'id': user_id, 'file_format': file_format}

    async def write_file(self, file_data: dict) -> None:
        """Saves the file sent by the client to disk"""
        if not os.path.exists('files'):
            os.mkdir('files')
        filename = '{0}-{1}.{2}'.format(file_data['name'], file_data['id'], file_data['file_format'])
        self.sent_files_to_user[filename] = [file_data['id']]
        if filename in self.files:
            self.files.remove(filename)
        self.files.append(filename)
        with open(f'files/{filename}', 'wb') as file:
            file.write(file_data['file'])

    async def read_file(self, filename: str) -> bytes:
        """Reads file data from disk to send it"""
        with open(f'files/{filename}', 'rb') as file:
            data = file.read()
        return data

    @swagger_path('swagger_docs/get_file.yaml')
    async def get_file(self, request: Request) -> Response:
        data = await request.read()
        file_data = await self.prepare_data_for_saving_file(data)
        await self.write_file(file_data)
        return Response()

    @swagger_path('swagger_docs/send_file.yaml')
    async def send_file(self, request: Request):
        client = ServersClientModel.parse_obj(await request.json())
        for file in self.files:
            if client.id in self.sent_files_to_user.get(file):
                continue
            self.sent_files_to_user[file].append(client.id)
            data = await self.read_file(file)
            from_user, file_format = file.split('.')
            text = f'from-{from_user}.{file_format}'
            return Response(body=text.encode() + data)
        return Response()

    def update_limit(self, client: ServersClientModel) -> bool:
        """
        Checks if the time required to update the message sending limit has passed.
        If the time has come, update the limit.
        """
        if client.limit_update_time < time.time():
            client.sent_messages = 0
            return True
        return False

    def set_msg_over_limit_status(self, client: ServersClientModel) -> None:
        """
        Checks if the limit for sending messages has been exceeded and, if exceeded, sets
        the limit exceeded status for the client.
        """
        if client.sent_messages >= MSG_LIMIT and not client.over_limit:
            client.over_limit = True
            client.limit_update_time = time.time() + LIMIT_UPDATE_PERIOD
        elif client.over_limit and self.update_limit(client):
            client.over_limit = False

    def add_to_msg_buffer(self, msg: MessageModel) -> None:
        """Store new message to buffer if buffer overflowed delete the oldest message"""
        if len(self.messages_bufer) < BUFFER_SIZE:
            self.messages_bufer.append(msg)
        else:
            self.messages_bufer.pop()
            self.messages_bufer.append(msg)

    def init_routes(self) -> None:
        self.app.add_routes([
            self.server.post('/send', self.get_message),
            self.server.post('/send-to', self.get_message_to_user),
            self.server.post('/connect', self.connect),
            self.server.get('/status', self.send_status),
            self.server.post('/get-messages', self.send_messages_to_users_from_buffer),
            self.server.post('/get-update', self.send_update),
            self.server.post('/close', self.del_client_from_connected_list),
            self.server.post('/send-file', self.get_file),
            self.server.post('/get-file', self.send_file)
        ])

    def run(self) -> None:
        self.init_routes()
        setup_swagger(self.app, swagger_url="/api/v1/doc", ui_version=2, title=TITLE)
        self.server.run_app(self.app, host=self.host, port=self.port)


if __name__ == '__main__':
    server = Server()
    server.run()
