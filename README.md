# Internal Knowledge RAG

A web-based RAG assistant that answers questions from internal company documents (HR policy, leave rules, store SOP, product catalog) and cites its sources. Built as a learning project for Month 3 of an AI engineering roadmap.

The documents used here are fictional, written for NUSAwear, a children's clothing store.

## What it does

- Reads a `.docx` document, converts tables into self-contained sentences, and keeps section context
- Splits the text into chunks with a prefix showing document and section, so each chunk can be understood on its own
- Embeds each chunk with `text-embedding-3-small` and stores the vectors in `knowledge.json`
- Retrieves the top chunks for a question using cosine similarity (numpy)
- Sends the retrieved chunks and the question to a chat model with instructions to answer only from those chunks, ask for clarification when a question has more than one meaning, and cite the source document
- Serves a chat web page with FastAPI, showing the sources used for each answer

## Project structure

```
docx_to_text.py    converts a .docx file into plain text, tables as sentences
knowledge.txt      converted document, input for chunking
main.py            chunking, embedding, storage, retrieval, answering
app.py             FastAPI app: chat endpoint, rate limit, logging
index.html         chat web page
Dockerfile         container build
knowledge.json     generated store (not committed)
tabel_eval_*.docx  manual evaluation table with results
```

## Setup

1. Create and activate a virtual environment:

   ```
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root:

   ```
   OPENAI_API_KEY=sk-xxxxxxxx
   ```

4. Convert the source document (optional, `knowledge.txt` is already included):

   ```
   python docx_to_text.py SOP_NUSAwear.docx knowledge.txt
   ```

The first run builds `knowledge.json`. To rebuild after editing `knowledge.txt`, delete `knowledge.json` first.

## Running

### Locally, with the web app

```
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

### Locally, from the terminal

```
python main.py
```

This runs a few fixed test questions and prints the answers and retrieved chunks.

### With Docker

```
docker build -t nusawear-rag .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-xxxxxxxx nusawear-rag
```

The API key is passed at runtime and is not stored in the image.

## Rate limiting

Each IP address is limited to **20 questions per 24 hours**. The 21st request receives a `429` response, and the rejection is logged.

Limitations of this approach:
- Counts are kept in memory and reset when the server restarts.
- The limit is per IP address, not per user. Shared networks such as offices or cafes share one quota.
- The `x-forwarded-for` header can be spoofed by clients, so this is not a strong security control.

To protect API costs, this limit is combined with a usage limit set in the OpenAI dashboard.

## Logging

Each successful question is logged with its length, the number of sources, and the response time:

```
2026-11-26 10:31:49,147 ask len=11 sources=5 ms=4489.5
```

Rejections due to the rate limit and failed requests are also logged, with a short message. Question text is not logged.

## Security and design decisions

- **No authentication yet.** The page is meant for public demo use, and visitors do not need an account. An API key authentication layer would be needed before exposing the endpoint to other applications.
- **The API key** is read only from an environment variable, never written in code or in the image.
- **Logs do not contain question text**, only question length and response time. Full error messages from the OpenAI library are not logged.
- **All documents in this project are fictional.** Review what appears in answers and logs before using real company documents.

## Evaluation

Results are recorded in a manual evaluation table (`tabel_eval_nusawear_v_final.docx`) with 25 questions. Each question was checked for:
- whether the right chunk appears in the top results (retrieval)
- whether the answer matches the document, with no invented numbers or rules (generation)
- for ambiguous questions, whether the model asks for clarification instead of picking one meaning
- for questions the document does not answer, whether the model says so

Current status: all questions pass at least once with full context. Some pass with notes, for example the model mentions working hours as context when asked about first-day arrival time.

## Problems found and fixed

- **Truncated context.** The first version sent only the first 200 characters of each chunk to the model. Numbers and deadlines near the end of a chunk were lost, so the model gave wrong answers ("09" instead of "09.30"). Full chunk text is now sent.
- **Wrong chunk for a question about customer service contact.** A customer-service phone number was in the document, but its chunk did not rank in the top 8. Adding the words "WhatsApp CS (Customer Service)" to the chunk text fixed it. An earlier attempt used a keyword list added to the chunk prefix, which worked but pulled unrelated chunks up. It was removed in favour of editing the source text.
- **Chunks mixing sections.** Section headers were carried into the wrong chunks. Numbered list items were sometimes read as section headers, and section numbers were sometimes read as step numbers. Parsing order was changed so headers are checked before step numbers.
- **Introductory lines separated from their rules.** A line such as "Pengajuan dilakukan... dengan ketentuan waktu minimal:" was stored without the rules that follow it. Introductory lines are now joined to the rule lines below them.

## Limitations

- **No deployment yet.** The app runs locally or in Docker only. Public hosting, and the usage limits that go with it, are still to be done.
- **Rate limit is in memory.** It resets on restart and is not a strong security control, as described above.
- **No authentication.** Anyone who can reach the server can use the API key until the usage limit is reached.
- **PDF tables cannot be extracted reliably.** The source was available as both PDF and DOCX. Tables in the PDF had no grid lines and wrapped cells, so automatic extraction misaligned columns. The project uses the DOCX version. Any new source should be converted to DOCX and checked before ingestion.
- **Chroma did not run on this machine.** Both `chromadb` 1.5.9 and 0.5.x failed (access violation on `add`, and a build error for `chroma-hnswlib` on Windows with an older Visual Studio toolchain). Storage and search use numpy instead. The code is small enough to move to a vector database later.
- **Reranking is not used.** Retrieval is a single embedding search. Some questions with two topics or similar wording rely on the top 5 or 8 results being enough.
- **Metadata filtering is available but not used for answers.** The query function accepts a filter on document or step number, but the current questions search all documents.
- **Scores are relative.** A similarity of 0.3 does not mean the chunk is irrelevant; the ranking matters. There is no threshold.
- **Evaluation is manual.** Every answer was read and judged by hand. There is no automated check yet.
- **The model is not deterministic.** The same question can be phrased differently between runs. Results were judged by meaning and facts, not wording.
- **Markdown in answers is not rendered.** The chat page shows `**bold**` as plain text. Fixing this needs a system prompt change or a markdown renderer.

## What I learned

- How chunking choices change retrieval: section context in the prefix, self-contained sentences for table rows, and joining introductory lines to their rules
- That a wrong answer can come from the pipeline, not the model: a truncated context looked like a model mistake until the cause was found
- Writing instructions that ask for clarification on ambiguous questions, and that say when a document does not contain an answer
- Keeping a manual evaluation table with a status and a note for each question, and re-running questions after every change
- Diagnosing a failing dependency (Chroma crash) to the native level and choosing an alternative with a clear reason
- Adding logging and rate limiting to an API, and recognising what the logs should and should not contain

## Built with

- Python 3.12
- OpenAI API (embeddings and chat)
- FastAPI and uvicorn
- numpy
- python-dotenv
- python-docx
- Docker