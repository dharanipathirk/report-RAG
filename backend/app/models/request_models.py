from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str


class QueryRequest(BaseModel):
    query: str


class LoginRequest(BaseModel):
    username: str
    password: str
