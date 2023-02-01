from pydantic import BaseModel


class ClientModel(BaseModel):
    name: str
    id: str


class MessageModel(ClientModel):
    file: bytes | None
    msg: str | None
    msg_id: int | None
    to_user: str | None


class ServersClientModel(ClientModel):
    banned: bool = False
    banned_till: float = 0
    sent_messages: int = 0
    limit_update_time: float = 0
    over_limit: bool = False
