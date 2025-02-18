# Report-RAG

A RAG chatbot prototype that combines Vision Language Model (ColQWen2) based retrieval with GPT-4o for business report analysis. **Currently experimental** - best-effort results with room for improvement.

## ▶️ How to Run

### Prerequisites
- NVIDIA GPU (16GB+ VRAM)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- Docker & Docker Compose
- OpenAI API key

### Setup
1. Clone repo and navigate to project root
2. Create `.env.production` from `.env.example`:
   ```bash
   cp .env.example .env.production
   ```
3. Edit `.env.production`:
   - Set `OPENAI_API_KEY`
   - Adjust other values as needed

### Launch
```bash
docker compose up --build
```
Access at `http://localhost:8000` after build completes (may take several minutes for initial embedding generation).

## 🛠️ Project Structure
```
Report-RAG/
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   └── requirements.txt
├── Data/
│   ├── [Sample PDFs]
│   ├── [Generated Embeddings]
│   ├── [Logs]
│   └── ...
├── docker-compose.yml
├── Dockerfile
└── frontend/
    └── static/
        ├── index.html
        ├── styles.css
        └── script.js
```

## 🔍 What is Report-RAG?
Combines two AI systems for document understanding:
1. **ColQWen2** (local GPU)
   - Leverages visual components to produce high-quality contextualized embeddings
   - ColBERT-style late interaction matching mechanism
   - *No OCR required* - understands layout/charts visually
2. **GPT-4o** (API)
   - Generates answers using retrieved pages
3. **Tesseract**
   - Highlights key text regions

**Features:**
- JWT auth (in-memory store)
- Pre-indexed PDFs + user uploads
- Top-2 page retrieval with highlights

## 📝 TODO
**Core Improvements**
- [ ] Chat history persistence
- [ ] Batch PDF upload support
- [ ] Enhanced highlight accuracy
- [ ] Better prompt engineering

**Technical Debt**
- [ ] Add test suite
- [ ] Proper user auth storage
- [ ] Optimize ColPali model memory usage

## ⚠️ Limitations (Prototype)
- Basic JWT implementation (in-memory)
- GPU memory intensive
- Simple frontend UI
- Accuracy varies with document types

For production use: Requires significant refinement of all components.

colqwen2 & Byaldi: The integration is subject to updates as Byaldi(pre-release) and ColPali-engine evolve. Keep track of library changes to maintain compatibility.
