import os
import json
import uuid
import asyncio
import logging

import aioconsole
from aiohttp import ClientSession

from logger_ import logging
from models import MessageModel, ClientModel
from config import settings


logger = logging.getLogger(__name__)


class Client:
    def __init__(self, server_host=settings.client_host,
                 server_port=settings.port,
                 client_session: ClientSession = ClientSession) -> None:
        self.name = None
        self.id = str(uuid.uuid4())
        self.client_model = None
        self.server_host = server_host
        self.server_port = server_port
        self.base_path = r'{0}:{1}/'.format(self.server_host, self.server_port)
        self.client_session = client_session
        self.sesion = None
        self.commands = {'@to': self.send_to, '@close': self.close}

    async def send(self, msg: str) -> None:
        """Send message to all users"""
        path = self.base_path + 'send'
        message = f'{self.name}: {msg}'
        try:
            msg_model = MessageModel(name=self.name, id=self.id, msg=message)
            resp = await self.sesion.post(path, data=msg_model.json())
            if await resp.text():
                print(await resp.text())
        except Exception as ex:
            logger.error(ex)

    async def send_to(self, data: str) -> None:
        """Send message for certain user"""
        path = self.base_path + 'sendto'
        _, to_user, *message = data.split(' ')
        if isinstance(message, list):
            message = ' '.join(message)
        try:
            msg = MessageModel(name=self.name, id=self.id, msg=message, to_user=to_user)
            await self.sesion.post(path, data=msg.json())
        except Exception as ex:
            logger.error(ex)

    async def connect(self) -> None:
        path = self.base_path + 'connect'
        try:
            self.sesion = self.client_session()
            resp = await self.sesion.post(path, data=self.client_model.json())
            logger.info('Connectection status: OK')
            text = await resp.text()
            print(text)
        except Exception as ex:
            logger.error(ex)

    async def get_update(self) -> None:
        """Get last unreceived messages"""
        path = self.base_path + 'getupdate'
        while not self.sesion.closed:
            try:
                resp = await self.sesion.post(path, data=self.client_model.json())
                text = await resp.text()
                if text and not text.startswith(self.name):
                    print(await resp.text())
                await asyncio.sleep(1)
            except Exception as ex:
                logger.error(ex)

    async def parse_command(self, msg: str) -> str:
        lst = msg.split(' ')
        command = lst[0]
        return command

    async def get_command_from_user(self) -> None:
        """Handle commands from user"""
        while not self.sesion.closed:
            try:
                msg = await aioconsole.ainput()
                if msg.startswith('@'):
                    command = await self.parse_command(msg)
                    coro = self.commands.get(command)
                    await coro(msg)
                else:
                    await self.send(msg)
            except Exception as ex:
                logger.error(ex)

    async def start(self) -> None:
        """Sends a connection request and starts an event loop"""
        await self.connect()
        await asyncio.gather(self.get_update(), self.get_command_from_user())

    def create_user(self) -> None:
        self.name = input('Enter your name: ')
        if not self.name:
            self.name = self.id
        self.client_model = ClientModel(name=self.name, id=self.id)
        with open(settings.client_info_filepath, 'w') as file:
            json.dump(self.client_model.dict(), file)

    def run(self) -> None:
        """
        Checks whether there is already a created user for this Client (checks for the presence of client.json),
        if there is none, it offers to create it.
        """
        if os.path.exists(settings.client_info_filepath):
            self.client_model = ClientModel.parse_file(settings.client_info_filepath)
            self.name = self.client_model.name
            self.id = self.client_model.id
        else:
            self.create_user()
        asyncio.run(self.start())

    async def close(self, *_) -> None:
        """Close connection and event loop"""
        path = self.base_path + 'close'
        await self.sesion.post(path, data=self.client_model.json())
        logger.info('Disconnected from the chat')
        await self.sesion.close()


if __name__ == '__main__':
    client = Client()
    client.run()
