from pathlib import Path

import openai
from fastapi import HTTPException, Request


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
        input_path=uploaded_path,
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


async def query_rag(request: Request, colpali_model):
    """
    Performs a Retrieval-Augmented Generation (RAG) query using the conversation history and the specified model.
    Summarizes previous conversation context if available, searches for relevant document chunks,
    and returns the answer along with document and page details.
    """
    data = await request.json()
    messages = data.get('messages', [])

    # Summarize previous conversation context if applicable.
    if len(messages) > 1:
        history_text = '\n'.join(msg.get('content', '') for msg in messages[:-1])
        summarization_prompt = (
            'Please summarize the following conversation context briefly. This will be sent to the RAG model for context.\n'
            'Note: This summarization is solely to maintain context in the query without affecting the RAG process. '
            'Provide only the essential context information.\n\n'
            f'Conversation Context:\n{history_text}'
        )

        summary_response = openai.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are a summarization assistant.'},
                {'role': 'user', 'content': summarization_prompt},
            ],
            temperature=0.3,
        )
        summary = summary_response.choices[0].message.content.strip()
    else:
        summary = ''

    # Prepare the final query by combining the summary with the current message.
    current_query = messages[-1].get('content', '')
    query = summary + '\n' + current_query if summary else current_query
    print(query)

    results = colpali_model.search(query, k=3)
    result_images = [result['base64'] for result in results]

    system_prompt = "You are an assistant that answers questions based on the provided image context. Answer the user's question as accurately as possible using the context below."

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

    completion = openai.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages_payload,
        temperature=0.3,
    )
    answer = completion.choices[0].message.content

    return {
        'answer': answer,
        'document used': results[0]['doc_id'],
        'page_used': results[0]['page_num'],
    }
