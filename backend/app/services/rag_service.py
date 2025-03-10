import asyncio
import datetime
from pathlib import Path

import aiofiles  # type: ignore
import openai
from app.utils.helper_functions import (
    extract_keywords,
    highlight_keywords_in_image,
    remove_keywords,
)
from fastapi import HTTPException, Request
from openai import APIError, APITimeoutError


async def process_pdf_upload(file, custom_pdf_model):
    """
    Processes an uploaded PDF file by saving it locally, indexing it using the custom PDF model,
    and computing embeddings.
    """
    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail='Only PDF files are allowed.')

    uploaded_path = (
        Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'uploaded'
    )
    uploaded_path.mkdir(parents=True, exist_ok=True)
    file_path = uploaded_path / file.filename

    with open(file_path, 'wb') as buffer:
        buffer.write(await file.read())

    custom_pdf_model.index(
        input_path=file_path,
        index_name='uploaded',
        store_collection_with_index=True,
        overwrite=True,
    )

    return {
        'message': 'PDF uploaded and processed',
    }


def process_reports(report_model):
    """
    Indexes reports from the raw data directory using the provided report model.
    """
    report_path = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'raw'
    report_model.index(
        input_path=report_path,
        index_name='reports',
        store_collection_with_index=True,
        overwrite=True,
    )


async def log_query(query: str):
    """
    Asynchronously appends the query along with a timestamp to a log file.
    The log file is stored in project/data/log/queries.log.
    """
    # Define the log directory and ensure it exists
    log_dir = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'log'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'queries.log'

    # Create a timezone-aware timestamp for the log entry
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Write the log entry asynchronously
    async with aiofiles.open(log_file, 'a') as f:
        await f.write(f'{timestamp}: {query}\n')


async def query_rag(request: Request, colpali_model):
    """
    Performs a Retrieval-Augmented Generation (RAG) query using the conversation history and the specified model.
    Summarizes previous conversation context if available, searches for relevant document chunks,
    and returns the answer along with document and page details.
    """
    data = await request.json()
    messages = data.get('messages', [])
    current_query = messages[-1].get('content', '')

    # Extract only the relevant context from the conversation history based on the current query.
    if len(messages) > 1:
        conversation_history = '\n'.join(
            msg.get('content', '') for msg in messages[:-1]
        )

        context_extraction_prompt = f"""
            Please read the conversation context below along with the current user query.
            From the conversation, identify and extract only the details that are directly relevant or necessary for answering the current query.
            Do not summarize the entire chat history; instead, focus on providing only the essential context needed to address the user’s question accurately.
            If certain parts of the conversation are unrelated, do not include them in your response.
            The extracted context should be a very concise summary of the relevant information.
            if the conversation history is not relevant to the current query, don't output anything. Don't say things like "No relevant context is available." or similar.

            Conversation Context:
            {conversation_history}

            Current Query:
            {current_query}
            """

        retry_delay = 0.5
        while True:
            try:
                context_extraction_response = openai.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {'role': 'system', 'content': 'You are a query rewriter...'},
                        {'role': 'user', 'content': context_extraction_prompt},
                    ],
                    temperature=0.1,
                )
                relevant_context = context_extraction_response.choices[
                    0
                ].message.content.strip()
                break
            except APITimeoutError as e:
                asyncio.create_task(
                    log_query(
                        f'Context injection timeout: {e}. Retrying in {retry_delay}s'
                    )
                )
                await asyncio.sleep(retry_delay)
            except APIError as e:
                if e.status_code in {502, 503, 504, 429}:
                    asyncio.create_task(
                        log_query(
                            f'Context injection error ({e.status_code}): {e}. Retrying in {retry_delay}s'
                        )
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    raise
            except Exception as e:
                asyncio.create_task(
                    log_query(f'Unexpected context injection error: {e}')
                )
                raise
    else:
        relevant_context = ''

    # Combine the extracted relevant context with the current query.
    query = (
        relevant_context + '\n' + current_query if relevant_context else current_query
    )
    asyncio.create_task(log_query(query))

    results = colpali_model.search(query, k=5)
    result_images = [result['base64'] for result in results]

    system_prompt = """You are an assistant that strictly answers questions based on information visibly present in the provided images of company business reports. Follow these rules:

                    1. If the answer cannot be conclusively found in the images, respond with:
                    "I couldn't find the relevant information in the provided report."

                    2. Never speculate, assume, or use knowledge outside of what is visible in the images.

                    3. For information found in the images:
                    - Provide a precise response using exact numbers/terms from the documents.
                    - At the end of your answer, highlight the key facts as keywords. Use this format:
                        **Keywords:** 'keyword1', 'keyword2', 'keyword3', ...
                    - Each keyword should be a single word (if a phrase exists in the document, split it into separate words).
                    - Keywords must reflect the core information in your response. If someone looks at the document and sees the keyword, it should match what you have stated.
                    - Preserve original numerical values and financial terminology.

                    Examples:

                    Q: What was the Q3 marketing budget of BMW?
                    A: The Q3 marketing budget of BMW was $2.45 million, representing 15% of operational expenses.
                    **Keywords:** 'BMW', 'Q3', '$2.45', 'million', '15%'

                    Q: What is the total salary for the CEO of Apple?
                    A: The total salary for the  of Apple is $1,321,368.
                    **Keywords:** 'Apple', 'CEO', '$1,321,368'

                    Q: What's our market share in Asia?
                    A: I couldn't find the relevant information in the provided report."""

    messages_payload = [
        {
            'role': 'system',
            'content': system_prompt,
        },
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': query},
                *map(
                    lambda x: {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{x}'},
                    },
                    result_images,
                ),
            ],
        },
    ]

    while True:
        try:
            completion = openai.chat.completions.create(
                model='gpt-4o', messages=messages_payload, temperature=0.2
            )
            answer = completion.choices[0].message.content
            break
        except APITimeoutError as e:
            asyncio.create_task(
                log_query(f'Completion timeout: {e}. Retrying in {retry_delay}s')
            )
            await asyncio.sleep(retry_delay)
        except APIError as e:
            if e.status_code in {502, 503, 504, 429}:
                asyncio.create_task(
                    log_query(
                        f'Completion error ({e.status_code}): {e}. Retrying in {retry_delay}s'
                    )
                )
                await asyncio.sleep(retry_delay)
            else:
                raise
        except Exception as e:
            asyncio.create_task(log_query(f'Unexpected completion error: {e}'))
            raise

    asyncio.create_task(log_query(answer))

    keywords = extract_keywords(answer)
    answer = remove_keywords(answer)

    if keywords:
        num_images_to_highlight = 2
        highlighted_images = [
            highlight_keywords_in_image(result_images[i], keywords)
            for i in range(min(num_images_to_highlight, len(result_images)))
        ]
    else:
        highlighted_images = []
        print('No keywords found in the answer.')

    return {
        'answer': answer,
        'highlighted_images': highlighted_images,
    }
