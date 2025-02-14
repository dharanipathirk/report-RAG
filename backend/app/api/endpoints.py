import os
import openai

from datetime import timedelta
from fastapi import (
    APIRouter,
    Request,
    Response,
    HTTPException,
    status,
    Depends,
    Form,
    UploadFile,
    File,
)
from fastapi.responses import StreamingResponse, FileResponse

from app.utils import auth
from app.services import rag_service

frontend_router = APIRouter()
api_router = APIRouter()

# Set the OpenAI API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")
env = os.getenv("ENV", "development")


@frontend_router.get("/config.js")
async def get_config():
    env = os.environ.get("ENV", "development")
    config = {"API_BASE": "http://localhost:8000" if env == "development" else ""}
    js_content = f"""
    window.APP_CONFIG = {{
        ENV: "{env}",
        API_BASE: "{config['API_BASE']}"
    }};
    """
    return Response(content=js_content, media_type="application/javascript")


@frontend_router.get("/")
async def read_index():
    return FileResponse("../frontend/static/index.html")


@api_router.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    user = auth.FAKE_USER_DB.get(username)
    if not user or not auth.verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="strict",
        secure=True if env == "production" else False,
        max_age=1800,
    )
    return {"message": "Login successful"}


@api_router.get("/validate-token")
def validate_token(request: Request):
    try:
        auth.get_current_user_from_cookie(request)
        return {"valid": True}
    except HTTPException:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)


@api_router.post("/chat")
async def chat(
    request: Request, user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Receives a JSON payload {"prompt": "..."} and streams a GPT response.
    """
    data = await request.json()
    user_prompt = data.get("prompt", "")

    response_stream = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.7,
        stream=True,
    )

    def stream_gpt():
        for chunk in response_stream:
            chunk_message = getattr(chunk.choices[0].delta, "content", "")
            if chunk_message:
                yield chunk_message

    return StreamingResponse(stream_gpt(), media_type="text/plain")


@api_router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...), user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Processes an uploaded PDF and computes embeddings.
    """
    result = await rag_service.process_pdf_upload(file)
    return result


@api_router.post("/query")
async def query_endpoint(
    query: str = Form(...), user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Retrieves relevant PDF chunks and returns an answer using GPT.
    """
    result = await rag_service.query_rag(query)
    return result
