import os
import json
import uuid
import asyncio
import logging

import aioconsole
from aiohttp import ClientSession

from config import LOGGER_SETTINGS, FILEPATH
from models import MessageModel, ClientModel


logging.basicConfig(**LOGGER_SETTINGS)
logger = logging.getLogger(__name__)


class Client:
    def __init__(self, server_host="127.0.0.1", server_port=8000, client_session: ClientSession = ClientSession) -> None:
        self.name = None
        self.id = str(uuid.uuid4())
        self.client_model = None
        self.server_host = server_host
        self.server_port = server_port
        self.base_path = r'http://{0}:{1}/'.format(self.server_host, self.server_port)
        self.client_session = client_session
        self.sesion = None
        self.messages_buffer = []

    async def send(self) -> None:
        if self.messages_buffer:
            message = self.messages_buffer.pop()
            if message.startswith('@'):
                path = self.base_path + 'send-to'
                try:
                    lst = message.split(' ')
                    to_user = lst[0][1:]
                    message = ' '.join(lst[1:])
                    msg = MessageModel(name=self.name, id=self.id, msg=message, to_user=to_user)
                    await self.sesion.post(path, data=msg.json())
                except Exception as ex:
                    logger.error(ex)
            else:
                path = self.base_path + 'send'
                try:
                    msg = MessageModel(name=self.name, id=self.id, msg=message)
                    await self.sesion.post(path, data=msg.json())
                except Exception as ex:
                    logger.error(ex)

    async def connect(self) -> None:
        path = self.base_path + 'connect'
        try:
            self.sesion = self.client_session()
            resp = await self.sesion.post(path, data=self.client_model.json())
            status = await resp.text()
            logger.info(f'Connectection status: {status}')
        except Exception as ex:
            logger.error(ex)

    async def get_messages_from_server_at_start(self) -> None:
        path = self.base_path + 'get-messages'
        try:
            resp = await self.sesion.post(path, data=self.client_model.json())
            text = await resp.text()
            if text and not text.startswith(self.name):
                print(await resp.text())
        except Exception as ex:
            logger.error(ex)

    async def send_message(self) -> None:
        while True:
            try:
                msg = await aioconsole.ainput()
                self.messages_buffer.append(msg)
                await self.send()
            except Exception as ex:
                logger.error(ex)

    async def get_update(self) -> None:
        path = self.base_path + 'get-update'
        while True:
            try:
                resp = await self.sesion.post(path, data=self.client_model.json())
                text = await resp.text()
                if text and not text.startswith(self.name):
                    print(await resp.text())
                await asyncio.sleep(0.2)
            except Exception as ex:
                logger.error(ex)

    async def start(self) -> None:
        await self.connect()
        await self.get_messages_from_server_at_start()
        await asyncio.gather(self.get_update(), self.send_message())

    def run(self) -> None:
        if os.path.exists(FILEPATH):
            self.client_model = ClientModel.parse_file(FILEPATH)
        else:
            self.name = input('Enter your name: ')
            if not self.name:
                self.name = self.id
            self.client_model = ClientModel(name=self.name, id=self.id)
            with open(FILEPATH, 'w') as file:
                json.dump(self.client_model.dict(), file)
        asyncio.run(self.start())

    async def on_close(self) -> None:
        path = self.base_path + 'close'
        await self.sesion.post(path, data=self.client_model)
        logger.info('Disconnected from the chat')
        await self.sesion.close()


if __name__ == '__main__':
    client = Client()
    client.run()
