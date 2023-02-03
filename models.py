from pydantic import BaseModel


class ClientModel(BaseModel):
    name: str
    id: str


class MessageModel(ClientModel):
    msg: str | None
    msg_id: int | None
    to_user: str | None


class ServersClientModel(ClientModel):
    last_got_msg_id: int = 0


class Request(BaseModel):
    method: str
    path: str
    body: bytes | None


class Response(BaseModel):
    status: str = '200 OK'
    http_v: str = 'HTTP/1.1'
    body: str | None
    text: str | None

    def _get_length(self) -> int:
        if self.body:
            return len(self.body.encode())
        elif self.text:
            return len(self.text.encode())
        return 0

    def _get_content_type(self) -> str:
        if self.text or not self.body:
            return 'text/plain'
        return 'application/json'

    def _get_body(self) -> str:
        if self.body:
            return self.body
        elif self.text:
            return self.text
        return None

    def create_response(self) -> bytes:
        content_type = self._get_content_type()
        content_length = self._get_length()
        body = self._get_body()
        if body:
            return f'{self.http_v} {self.status}\nContent-Type: {content_type}\nContent-Length: {content_length}\n\n{body}'.encode()
        return f'{self.http_v} {self.status}\nContent-Type: {content_type}\nContent-Length: {content_length}\n\n'.encode()
