# Virtual Try-On MVP

Privacy-first virtual try-on system cho phép người dùng visualize việc mặc quần áo từ Shopee thông qua AI-powered analysis.

## Features

- **Privacy Guard (Module 1)**: Face anonymization local với InsightFace trước khi upload
- **Semantic Parser (Module 2)**: AI analysis với OpenAI GPT-4o Vision
- **FastAPI Backend**: Async API server với type safety
- **Memory Management**: Auto-cleanup để prevent memory leaks
- **Error Handling**: Retry logic cho API calls và graceful degradation

## Architecture

```
User Image → Face Detection → Face Anonymization → Metadata Strip → API Ready
                                    ↓
Product Image + Anonymized User Image → OpenAI GPT-4o Vision → Analysis
                                                                    ↓
                                    {clothing_description, body_pose, inpainting_prompt}
```

## Requirements

- Python 3.11+
- OpenAI API key
- MacBook (Apple Silicon optimized) hoặc Linux/Windows

## Quick Start

### 1. Setup Environment

```bash
# Clone repository
cd tryon-visual-project

# Run setup script
make setup

# Or manually:
python3 scripts/setup_env.py
```

### 2. Configure API Keys

Edit `.env` file:

```bash
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### 3. Run Server

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
.\\venv\\Scripts\\activate  # Windows

# Start server
make run

# Or manually:
python -m uvicorn src.main:app --reload
```

Server will start at `http://127.0.0.1:8000`

API Documentation: `http://127.0.0.1:8000/docs`

## API Usage

### 1. Anonymize User Image

```bash
curl -X POST http://127.0.0.1:8000/api/v1/privacy/anonymize \\
  -F "file=@user_photo.jpg" \\
  -F "return_format=base64" \\
  > anonymized_response.json
```

Response:
```json
{
  "success": true,
  "faces_detected": 1,
  "anonymized_image": "base64_encoded_image...",
  "format": "base64",
  "message": "Image anonymized successfully. All metadata removed."
}
```

### 2. Analyze VTO Context

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/vto-context \\
  -H "X-User-Consent: true" \\
  -H "X-Image-Anonymized: true" \\
  -H "Content-Type: application/json" \\
  -d '{
    "anonymized_user_image": "base64...",
    "product_image": "base64..."
  }'
```

Response:
```json
{
  "success": true,
  "analysis": {
    "clothing_description": "A navy blue cotton t-shirt with crew neck...",
    "body_pose": "Standing straight with arms at sides...",
    "inpainting_prompt": "A navy blue cotton t-shirt worn by a person...",
    "confidence_score": 0.95
  },
  "message": "Analysis completed successfully"
}
```

## Development

### Available Commands

```bash
make setup      # Setup environment và download models
make run        # Run FastAPI server
make test       # Run tests với coverage
make lint       # Run linters (ruff + mypy)
make format     # Format code (black + ruff)
make check      # Run all checks (format + lint + test)
make clean      # Clean temporary files
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_privacy_guard.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Run all checks
make check
```

## Project Structure

```
tryon-visual-project/
├── src/
│   ├── main.py                          # FastAPI entry point
│   ├── config/settings.py               # Configuration management
│   ├── modules/
│   │   ├── privacy_guard/               # Face anonymization
│   │   │   ├── face_detector.py
│   │   │   ├── face_anonymizer.py
│   │   │   └── metadata_stripper.py
│   │   └── semantic_parser/             # AI analysis
│   │       ├── openai_client.py
│   │       └── prompt_builder.py
│   ├── api/routes/                      # API endpoints
│   ├── schemas/                         # Pydantic models
│   └── utils/                           # Utilities
├── tests/                               # Test suite
├── scripts/                             # Setup scripts
├── requirements.txt                     # Dependencies
└── Makefile                             # Dev commands
```

## Privacy & Security

- **Local Face Anonymization**: All face processing happens locally before any network calls
- **Metadata Stripping**: EXIF data removed from all images
- **User Consent**: Explicit consent required via API headers
- **Memory Cleanup**: Automatic cleanup after each request
- **No Data Storage**: All processing in-memory only

## Technology Stack

- **FastAPI**: Async web framework
- **InsightFace**: Face detection và swapping (buffalo_l + inswapper_128)
- **OpenAI GPT-4o Vision**: Semantic analysis
- **Pydantic**: Type validation và settings management
- **ONNX Runtime**: ML model inference (CPU-optimized)

## Troubleshooting

### InsightFace Model Download Fails

```bash
# Manually download models
python scripts/download_models.py
```

### OpenAI API Rate Limits

The system has built-in retry logic với exponential backoff. Check logs for retry attempts.

### Memory Issues

Adjust upload size limit trong `.env`:

```bash
MAX_UPLOAD_SIZE_MB=5
```

## Future Enhancements

- **Module 3**: Image Generation với DALL-E 3 / Imagen 3
- **Module 4**: Go Backend Gateway với worker pools
- **Neutral Face Library**: Multiple AI-generated neutral faces
- **Docker Support**: Containerization cho production deployment

## License

Private project - All rights reserved

## Support

For issues and questions, check:
- API Documentation: `http://127.0.0.1:8000/docs`
- Implementation Plan: `.claude/plans/glittery-inventing-toucan.md`
