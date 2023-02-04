from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    buffer_size: int = Field(20)
    client_info_filepath: str = Field('client.json')
    client_host: str = Field('http://127.0.0.1')
    server_host: str = Field('127.0.0.1')
    port: int = Field(8000)


settings = Settings()
