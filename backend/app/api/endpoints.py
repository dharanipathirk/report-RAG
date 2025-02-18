import os
from datetime import timedelta
from pathlib import Path

import openai
from app.services import rag_service
from app.services.rag_service import process_reports
from app.utils import auth
from byaldi import RAGMultiModalModel
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse

frontend_router = APIRouter()
api_router = APIRouter()

# Set OpenAI API key from environment variable.
openai.api_key = os.getenv('OPENAI_API_KEY')
env = os.getenv('ENV', 'development')

index_root = (
    Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'embeddings'
)

custom_pdf_model = RAGMultiModalModel.from_pretrained(
    'vidore/colqwen2-v1.0', index_root=index_root
)

report_model = RAGMultiModalModel.from_pretrained(
    'vidore/colqwen2-v1.0', index_root=index_root
)

process_reports(report_model)


@frontend_router.get('/config.js')
async def get_config():
    """
    Returns a JavaScript configuration file with API base URL and environment settings.
    """
    env = os.environ.get('ENV', 'development')
    config = {'API_BASE': 'http://localhost:8000' if env == 'development' else ''}
    js_content = f"""
    window.APP_CONFIG = {{
        ENV: "{env}",
        API_BASE: "{config['API_BASE']}"
    }};
    """
    return Response(content=js_content, media_type='application/javascript')


@frontend_router.get('/')
async def read_index():
    """
    Serves the main index.html file for the frontend.
    """
    return FileResponse('../frontend/static/index.html')


@api_router.post('/login')
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    """
    Authenticates a user and sets a secure cookie with an access token.
    """
    user = auth.FAKE_USER_DB.get(username)
    if not user or not auth.verify_password(password, user['hashed_password']):
        raise HTTPException(status_code=400, detail='Incorrect username or password')

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={'sub': user['username']}, expires_delta=access_token_expires
    )

    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        samesite='strict',
        secure=True if env == 'production' else False,
        max_age=1800,
    )
    return {'message': 'Login successful'}


@api_router.get('/validate-token')
def validate_token(request: Request):
    """
    Validates the user's access token from cookies.
    """
    try:
        auth.get_current_user_from_cookie(request)
        return {'valid': True}
    except HTTPException:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)


@api_router.post('/chat')
async def chat(
    request: Request, user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Receives a JSON payload with chat messages and streams a GPT response.
    Expected payload format: {"messages": [...]}
    """
    data = await request.json()
    messages = data.get('messages', [])
    if not messages:
        raise HTTPException(status_code=400, detail='No messages provided.')

    response_stream = openai.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        temperature=0.7,
        stream=True,
    )

    def stream_gpt():
        for chunk in response_stream:
            chunk_message = getattr(chunk.choices[0].delta, 'content', '')
            if chunk_message:
                yield chunk_message

    return StreamingResponse(stream_gpt(), media_type='text/plain')


@api_router.post('/upload-pdf')
async def upload_pdf(
    file: UploadFile = File(...), user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Processes an uploaded PDF file and computes embeddings using the custom PDF model.
    """
    # Reinitialize the custom PDF model to re-index it with the newly uploaded PDF.
    global custom_pdf_model
    custom_pdf_model = RAGMultiModalModel.from_pretrained(
        'vidore/colqwen2-v1.0', index_root=index_root
    )
    result = await rag_service.process_pdf_upload(file, custom_pdf_model)
    return result


@api_router.post('/custom-pdf-query')
async def custom_pdf_query_endpoint(
    request: Request, user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Retrieves relevant PDF chunks using the custom PDF model and returns an answer.
    """
    result = await rag_service.query_rag(request, custom_pdf_model)
    return result


@api_router.post('/report-query')
async def report_query_endpoint(
    request: Request, user: str = Depends(auth.get_current_user_from_cookie)
):
    """
    Processes a report query using the report model via RAG.
    """
    result = await rag_service.query_rag(request, report_model)
    return result
