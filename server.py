import logging

from aiohttp import web
from aiohttp.web import Response, Application, Request

from config import LOGGER_SETTINGS, BUFFER_SIZE
from models import MessageModel, ClientModel


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
        self.msg_id = -1
        self.client_id_of_last_received_msg = {}
        self.msg_to_user = {}

    async def send_status(self, request: Request) -> None:
        number = len(self.connected_clients)
        return Response(text=f'Status: OK. There is/are {number} user/s in the chat')

    async def connect(self, request: Request) -> None:
        client = ClientModel.parse_obj(await request.json())
        self.connected_clients.append(client)
        return Response(text='Connected')

    async def get_message(self, request: Request) -> None:
        msg = MessageModel.parse_obj(await request.json())
        self.msg_id += 1
        msg.msg_id = self.msg_id
        if len(self.messages_bufer) < BUFFER_SIZE:
            self.messages_bufer.append(msg)
        return Response()

    async def get_message_to_user(self, request: Request) -> None:
        msg = MessageModel.parse_obj(await request.json())
        to_user = msg.to_user
        self.msg_to_user[to_user] = f'***{msg.name}***: {msg.msg}'
        return Response()

    async def send_messages_to_users_from_buffer(self, request: Request) -> None:
        client = ClientModel.parse_obj(await request.json())
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

    async def send_update(self, request: Request) -> None:
        client = ClientModel.parse_obj(await request.json())
        if self.msg_to_user.get(client.name, None):
            msg = self.msg_to_user.get(client.name)
            return Response(text=msg)
        last_send_msg_id = self.client_id_of_last_received_msg.get(client.id, 0)
        for m in self.messages_bufer:
            if m.msg_id > last_send_msg_id:
                self.client_id_of_last_received_msg[client.id] = m.msg_id
                return Response(text=f'{m.name}: {m.msg}')
        return Response(text=msg)

    async def del_client_from_connected_list(self, request: Request) -> None:
        client = ClientModel.parse_obj(await request.json())
        self.connected_clients.remove(client)
        return Response()

    def init_routes(self) -> None:
        self.app.add_routes([
            self.server.post('/send', self.get_message),
            self.server.post('/send-to', self.get_message_to_user),
            self.server.post('/connect', self.connect),
            self.server.get('/status', self.send_status),
            self.server.post('/get-messages', self.send_messages_to_users_from_buffer),
            self.server.post('/get-update', self.send_update),
            self.server.post('/close', self.del_client_from_connected_list)
        ])

    def run(self) -> None:
        self.init_routes()
        self.server.run_app(self.app, host=self.host, port=self.port)


if __name__ == '__main__':
    server = Server()
    server.run()
