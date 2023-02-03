from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    buffer_size: int = Field(20)
    client_info_filepath: str = Field('client.json')
    limit_update_period: int = Field(60 * 60)  # seconds
    file_size_limit: int = Field(5000 * 1000)  # bytes
    client_host: str = Field('http://127.0.0.1')
    server_host: str = Field('127.0.0.1')
    port: int = Field(8000)


settings = Settings()
