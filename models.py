from pydantic import BaseModel


class ClientModel(BaseModel):
    name: str
    id: str
    banned: bool | None


class MessageModel(ClientModel):
    msg: str
    msg_id: int | None
    to_user: str | None
