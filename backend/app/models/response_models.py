from pydantic import BaseModel


class TokenResponse(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str


class QueryResponse(BaseModel):
    answer: str
    context_used: str


class GenericResponse(BaseModel):
    message: str
