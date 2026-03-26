# NucleoSize

A FastAPI-based microservice that exposes an HTTP API for retrieving nucleic acid sequence lengths from the Protein Data Bank (PDB).

## Overview

This service provides a simple REST API to query the total length of nucleic acid sequences for any PDB structure. It automatically syncs with PDB's weekly updates and maintains a local cache for fast responses.

## Features

- **REST API**: Simple endpoint to query nucleic acid lengths by PDB ID
- **Automatic Updates**: Checks for new PDB data every 6 hours with conditional GET (respects ETag/Last-Modified headers)
- **Efficient Caching**: Maintains local cache in `/data` volume that survives container restarts
- **Docker Support**: Easy deployment with Docker Compose
- **Streaming Download**: Memory-efficient parsing of large PDB sequence files
- **Atomic Updates**: Ensures data consistency during updates

## Quick Start

### Using Docker (Recommended)

```bash
# Build and run
docker-compose up --build

# Run in detached mode
docker-compose up -d --build
```

The API will be available at `http://localhost:8000`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Get Nucleic Acid Length

```
GET /api/{pdbid}
```

Returns the total length of all nucleic acid sequences for the specified PDB structure.

**Parameters:**

- `pdbid` (path): PDB ID (case-insensitive, e.g., `1abc` or `1ABC`)

**Response (200 OK):**

```json
{
  "pdbid": "1abc",
  "total_na_length": 42
}
```

**Error (404 Not Found):**

```json
{
  "detail": "PDB ID not found or contains no nucleic acids"
}
```

**Example:**

```bash
curl http://localhost:8000/api/1abc
```

### API Documentation

Interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Data Updates

The service automatically:

1. **On startup**: Checks for updates and downloads data if needed
2. **Every 6 hours**: Polls PDB for new data (4x daily to catch Wednesday updates)
3. **Conditional GET**: Uses ETag and If-Modified-Since to avoid unnecessary downloads
4. **Atomic writes**: Updates are performed atomically to prevent data corruption

Data is sourced from: `https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt`

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI     │────▶│  In-Memory  │
│             │◄────│  (main.py)   │◄────│    Cache    │
└─────────────┘     └──────────────┘     └─────────────┘
                             │                  │
                             ▼                  │
                      ┌──────────────┐          │
                      │   Periodic   │          │
                      │   Updater    │          │
                      └──────────────┘          │
                             │                  │
                             ▼                  ▼
                      ┌──────────────┐   ┌─────────────┐
                      │  PDB FTP     │   │  /data      │
                      │  Server      │   │  (Volume)   │
                      └──────────────┘   └─────────────┘
```

## Project Structure

```
.
├── main.py              # FastAPI application
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── requirements.in      # High-level dependencies
├── requirements.txt     # Pinned dependencies (auto-generated)
└── data/                # Persisted data (Docker volume)
    ├── na_lengths.json      # Cached nucleic acid lengths
    └── metadata.json        # ETag and Last-Modified headers
```

## Development

### Lint and Format

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Adding Dependencies

Edit `requirements.in` and run:

```bash
pip-compile requirements.in
```

## Configuration

The service can be configured via environment variables:

| Variable         | Default                                                       | Description           |
| ---------------- | ------------------------------------------------------------- | --------------------- |
| `DATA_FILE`      | `/data/na_lengths.json`                                       | Path to cache file    |
| `METADATA_FILE`  | `/data/metadata.json`                                         | Path to metadata file |
| `PDB_SEQRES_URL` | `https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt` | PDB data source       |

## Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- **HTTP Client**: [httpx](https://www.python-httpx.org/) - Async HTTP client with streaming support
- **Server**: [Uvicorn](https://www.uvicorn.org/) - Lightning-fast ASGI server
- **Python**: 3.13+
- **Docker**: Multi-stage build with Python 3.14-slim

## License

MIT License

---

**Data Source**: [Worldwide Protein Data Bank (wwPDB)](https://www.wwpdb.org/)
