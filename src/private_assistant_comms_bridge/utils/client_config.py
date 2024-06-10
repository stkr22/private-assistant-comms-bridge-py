from pydantic import BaseModel


class ClientConfig(BaseModel):
    samplerate: int
    channels: int
    chunk_size: int
    room: str
