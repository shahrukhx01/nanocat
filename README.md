# Nanocat

🐱 A minimal implementation of [pipecat](https://github.com/pipecat-ai/pipecat) for learning and educational purposes.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Create a virtual environment and install dependencies:
```bash
uv venv && uv pip install -e .
```

### Running the Application

The application consists of a backend server and a frontend interface.

1. Start the backend server:
```bash
uvicorn main:app --host localhost --port 8765 --reload
```

2. Start the frontend server:
```bash
uv run python -m http.server
```

3. Access the application by opening your browser and navigating to:
```
http://localhost:8000
```

## About

Nanocat is an educational project that recreates a simplified version of pipecat - an open-source framework for building voice and multimodal conversational agents. While pipecat offers a comprehensive suite of features for production use, nanocat focuses on implementing core voice bot functionality to help developers:

- Understand how pipecat is engineered under the hood
- Learn the internals and architecture of voice agent systems
- Get hands-on experience with fundamental voice AI concepts
- Explore a minimal working implementation without the complexity of a full production framework

This project serves as both a learning resource and a starting point for those interested in voice AI development or contributing to pipecat itself.
