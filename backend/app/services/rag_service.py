import io
import numpy as np
import faiss
import openai
import pypdf
from fastapi import HTTPException

# For the text-embedding model, the embedding dimension is 1536.
embedding_dim = 1536

# Global variables for the FAISS vector store and PDF metadata.
vector_index = faiss.IndexFlatL2(embedding_dim)
chunk_metadata = []  # List of dicts: {"doc_id": int, "page": int, "text": str}
pdf_counter = 0
pdf_docs = {}  # Maps doc_id to {"filename": str, "num_pages": int}


async def process_pdf_upload(file):
    """
    Reads a PDF file, extracts text per page, computes embeddings,
    and updates the FAISS vector store and metadata.
    """
    global vector_index, chunk_metadata, pdf_counter, pdf_docs

    # Reset globals for this upload
    vector_index = faiss.IndexFlatL2(embedding_dim)
    chunk_metadata = []
    pdf_counter = 0
    pdf_docs = {}

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    pdf_bytes = await file.read()
    pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

    if len(pdf_reader.pages) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF file.")

    pages_text = []
    valid_page_numbers = []  # Track pages with non-empty text
    for i, page in enumerate(pdf_reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text.strip())
            valid_page_numbers.append(i)

    if not pages_text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF.")

    # Compute embeddings for the extracted page texts.
    embedding_response = openai.embeddings.create(
        input=pages_text, model="text-embedding-3-small"
    )

    doc_id = pdf_counter
    pdf_counter += 1
    pdf_docs[doc_id] = {"filename": file.filename, "num_pages": len(pdf_reader.pages)}

    # Add each embedding and its metadata to the vector store.
    for page_num, embed_data, chunk_text in zip(
        valid_page_numbers, embedding_response.data, pages_text
    ):
        embedding_vector = np.array(embed_data.embedding, dtype=np.float32)
        embedding_vector = np.expand_dims(embedding_vector, axis=0)
        vector_index.add(embedding_vector)
        chunk_metadata.append(
            {
                "doc_id": doc_id,
                "page": page_num + 1,  # 1-indexed page number
                "text": chunk_text,
            }
        )

    return {
        "message": f"PDF uploaded and processed. Document ID: {doc_id}",
        "chunks_added": len(pages_text),
    }


async def query_rag(query: str):
    """
    Computes the query embedding, retrieves the most similar text chunks,
    and generates an answer using GPT.
    """
    global vector_index, chunk_metadata, pdf_docs

    if vector_index.ntotal == 0:
        raise HTTPException(
            status_code=400, detail="No documents available for querying."
        )

    query_embedding_response = openai.embeddings.create(
        input=[query], model="text-embedding-3-small"
    )
    query_embedding = query_embedding_response.data[0].embedding
    query_embedding_np = np.array(query_embedding, dtype=np.float32)
    query_embedding_np = np.expand_dims(query_embedding_np, axis=0)

    # Retrieve the top k nearest chunks.
    k = 5
    distances, indices = vector_index.search(query_embedding_np, k)

    retrieved_chunks = []
    for idx in indices[0]:
        if idx == -1 or idx >= len(chunk_metadata):
            continue
        retrieved_chunks.append(chunk_metadata[idx])

    if not retrieved_chunks:
        raise HTTPException(status_code=400, detail="No relevant context found.")

    # Combine retrieved chunks into a single context string.
    context_parts = []
    for chunk in retrieved_chunks:
        context_parts.append(
            f"Document {chunk['doc_id']} (Page {chunk['page']}):\n{chunk['text']}"
        )
    context_text = "\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions based on the provided context. "
                "Answer the user's question as accurately as possible using the context below."
                "\n\nContext:\n" + context_text
            ),
        },
        {"role": "user", "content": query},
    ]

    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )
    answer = completion.choices[0].message.content

    return {"answer": answer, "context_used": context_text}
