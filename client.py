import re
import os
import json
import uuid
import asyncio
import logging

import aioconsole
from aiohttp import ClientSession

from config import LOGGER_SETTINGS, FILEPATH, SIZE_LIMIT
from models import MessageModel, ClientModel


logging.basicConfig(**LOGGER_SETTINGS)
logger = logging.getLogger(__name__)


class Client:
    def __init__(self, server_host="http://127.0.0.1", server_port=8000, client_session: ClientSession = ClientSession) -> None:
        self.name = None
        self.id = str(uuid.uuid4())
        self.allow_download_files = False
        self.client_model = None
        self.server_host = server_host
        self.server_port = server_port
        self.base_path = r'{0}:{1}/'.format(self.server_host, self.server_port)
        self.client_session = client_session
        self.sesion = None
        self.commands = {'@to': self.send_to, '@close': self.close, '@file': self.send_file}

    async def send(self, message: str) -> None:
        """Send message to all users"""
        path = self.base_path + 'send'
        try:
            msg = MessageModel(name=self.name, id=self.id, msg=message)
            resp = await self.sesion.post(path, data=msg.json())
            if await resp.text():
                print(await resp.text())
        except Exception as ex:
            logger.error(ex)

    async def send_to(self, data: list) -> None:
        """Send message for certain user"""
        path = self.base_path + 'send-to'
        try:
            to_user = data[1]
            message = data[2]
            msg = MessageModel(name=self.name, id=self.id, msg=message, to_user=to_user)
            resp = await self.sesion.post(path, data=msg.dict())
            if await resp.text():
                print(await resp.text())
        except Exception as ex:
            logger.error(ex)

    def read_file(self, filepath: str):
        with open(filepath, 'rb') as file:
            data = file.read()
        return data

    async def write_file(self, data: bytes, filename: str) -> None:
        with open(filename, 'wb') as file:
            file.write(data)
        lst = filename.split('-')
        print(f'***Downloaded file from [{lst[1]}]')

    async def check_file_size(self, filepath) -> bool:
        if os.path.getsize(filepath) < SIZE_LIMIT:
            return True
        return False

    async def send_file(self, data: list) -> None:
        """Send file to all users"""
        path = self.base_path + 'send-file'
        if await self.check_file_size(data[1]):
            try:
                file = self.read_file(data[1])
                file_format = data[1].split('.')[-1]
                # Отправка файла возможна только в формате dict -> {'file_info': bytes}
                await self.sesion.post(path, data={f'{self.name} {self.id} {file_format}': file})
            except Exception as ex:
                logger.info(ex)
        else:
            print(f'!!!File is too large. Max size {SIZE_LIMIT} bytes')

    async def connect(self) -> None:
        path = self.base_path + 'connect'
        try:
            self.sesion = self.client_session()
            resp = await self.sesion.post(path, data=self.client_model.json())
            status = await resp.text()
            logger.info(f'Connectection status: {status}')
        except Exception as ex:
            logger.error(ex)
        return True

    async def get_file(self):
        """Downloade files sent by users"""
        path = self.base_path + 'get-file'
        while not self.sesion.closed:
            try:
                resp = await self.sesion.post(path, data=self.client_model.json())
                data = await resp.read()
                if data:
                    filename = re.findall(b'\w*-\w*-\w*-\w*-\w*-\w*-\w*\.\w*', data)[0]  # noqa: W605
                    data = data[len(filename):]
                    await self.write_file(data, filename.decode())
            except Exception as ex:
                logger.error(ex)
            await asyncio.sleep(2)

    async def get_messages_from_server_at_start(self) -> None:
        """Gets all latest messages on first connection"""
        path = self.base_path + 'get-messages'
        try:
            resp = await self.sesion.post(path, data=self.client_model.json())
            text = await resp.text()
            if text and not text.startswith(self.name):
                print(await resp.text())
        except Exception as ex:
            logger.error(ex)

    async def get_command_from_user(self) -> None:
        """Handle commands from user"""
        while not self.sesion.closed:
            try:
                msg = await aioconsole.ainput()
                if msg.startswith('@'):
                    lst = msg.split(' ')
                    if coro := self.commands.get(lst[0]):
                        await coro(lst)
                else:
                    await self.send(msg)
            except Exception as ex:
                logger.error(ex)

    async def get_update(self) -> None:
        """Get last unreceived messages"""
        path = self.base_path + 'get-update'
        while not self.sesion.closed:
            try:
                resp = await self.sesion.post(path, data=self.client_model.json())
                text = await resp.text()
                if text and not text.startswith(self.name):
                    print(await resp.text())
                await asyncio.sleep(0.3)
            except Exception as ex:
                logger.error(ex)

    async def start(self) -> None:
        if await self.connect():
            await self.get_messages_from_server_at_start()
            if self.allow_download_files:
                await asyncio.gather(self.get_command_from_user(), self.get_file())
            else:
                await asyncio.gather(self.get_command_from_user())

    def run(self) -> None:
        if os.path.exists(FILEPATH + '1'):
            self.client_model = ClientModel.parse_file(FILEPATH)
        else:
            self.name = input('Enter your name: ')
            if not self.name:
                self.name = self.id
            answer = input('Allow to download files from users?[y/n]: ')
            if answer.lower() == 'y':
                self.allow_download_files = True
            self.client_model = ClientModel(name=self.name, id=self.id)
            with open(FILEPATH, 'w') as file:
                json.dump(self.client_model.dict(), file)
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
