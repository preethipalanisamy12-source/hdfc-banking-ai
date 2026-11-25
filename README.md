# HDFC Banking AI Assistant

An AI-powered banking assistant built using Generative AI, Retrieval-Augmented Generation (RAG), and a fine-tuned language model.

## 1. Project Overview

HDFC Banking AI Assistant is a conversational application designed to help users interact with banking information through natural language.

The system combines an AI-powered intent router, a retrieval-based knowledge system, and a language model to provide relevant responses through a simple web interface.

## 2. Problem Statement

Banking information can be spread across multiple documents and services, making it difficult for users to find relevant answers quickly.

This project explores how Generative AI and RAG can make banking information easier to access through a conversational interface.

## 3. Key Features

- Conversational banking assistant
- AI-based intent detection and routing
- Retrieval-Augmented Generation (RAG)
- Knowledge-based question answering
- User authentication and session management
- Chat interface with a web frontend
- Backend API built with FastAPI

## 4. System Architecture

The application is organised into four main components:

- **Frontend:** HTML, CSS, and JavaScript interface
- **Backend:** FastAPI application handling requests and application logic
- **AI Layer:** Intent routing, language-model integration, and response generation
- **RAG Layer:** Document ingestion, embeddings, retrieval, and evaluation

## 5. Technology Stack

| Component | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| AI | Fine-tuned language model, Qwen |
| RAG | Sentence Transformers, BM25, vector retrieval |
| Database | SQLAlchemy, PostgreSQL-compatible configuration |
| Development | VS Code, Google Colab, GitHub |

## 6. Project Structure

```text
hdfc-banking-ai/
├── backend/
│   ├── app/
│   ├── data/
│   ├── rag/
│   ├── tests/
│   └── requirements.txt
├── frontend/
├── database/
├── shared/
├── colab/
├── .env.example
├── .gitignore
└── README.md
```

## 7. Local Setup

### Prerequisites

- Python 3.10+
- Git
- A configured model API endpoint

### Installation

Clone the repository:

```bash
git clone https://github.com/preethipalanisamy12-source/hdfc-banking-ai.git
cd hdfc-banking-ai
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Configure environment variables using the example file:

```text
backend/.env.example
```

Create a private `backend/.env` and enter your own configuration values. Never upload API tokens or secrets.

### Run the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

## 8. Model Integration

The language model is integrated through an API endpoint. The model experimentation and integration workflow is documented in the `colab/` directory.

## 9. Evaluation

The project includes evaluation scripts and test cases for:

- Retrieval performance
- Embedding model comparison
- Intent routing
- Backend services
- API and application functionality

## 10. Security and Limitations

- This is an educational demonstration, not an official HDFC Bank product.
- The application does not connect to real customer banking accounts.
- Demonstration data should not be treated as verified or authoritative HDFC Bank policy.
- Model responses may be inaccurate and should not be used for actual financial decisions.
- API credentials and private environment files must never be committed to GitHub.

## 11. Future Improvements

- Improve retrieval accuracy and response quality
- Expand automated testing and evaluation
- Improve deployment and scalability
- Strengthen response validation and error handling

## 12. Repository

GitHub: https://github.com/preethipalanisamy12-source/hdfc-banking-ai
