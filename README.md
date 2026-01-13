# Konozy AI Enterprise

> **Enterprise-grade Domain-Driven Design (DDD) / Hexagonal Architecture implementation with FastAPI**

[![Architecture Violations](https://img.shields.io/badge/Architecture-Violations:0-success)](./scripts/run_architecture_check.sh)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-orange.svg)](https://www.sqlalchemy.org/)

## 🏗️ Architecture Overview

This project implements **Clean Architecture** (Hexagonal Architecture / DDD) with strict layer separation and dependency inversion principles.

### Architectural Layers

```
┌─────────────────────────────────────────┐
│   Presentation Layer (FastAPI)          │  ← apps/api/
│   - REST API Endpoints                  │
│   - Request/Response DTOs               │
└─────────────────┬───────────────────────┘
                  │ depends on
┌─────────────────▼───────────────────────┐
│   Application Layer                     │  ← core/application/
│   - Application Services                │
│   - Use Cases                           │
│   - Pydantic DTOs                       │
└─────────────────┬───────────────────────┘
                  │ depends on
┌─────────────────▼───────────────────────┐
│   Domain Layer (PURE)                   │  ← core/domain/
│   - Entities                            │  ⚠️ ZERO framework dependencies
│   - Value Objects                       │
│   - Repository Interfaces (ABC)         │
└─────────────────┬───────────────────────┘
                  ↑ implemented by
┌─────────────────┴───────────────────────┐
│   Infrastructure Layer                  │  ← core/data/
│   - SQLAlchemy Models                   │
│   - Repository Implementations          │
│   - Static Mappers                      │
│   - Unit of Work (UoW)                  │
└─────────────────────────────────────────┘
```

### 🛡️ Domain Purity Law (ZERO TOLERANCE)

The `core/domain/` directory is **STRICTLY PURE** and must NOT contain:

- ❌ SQLAlchemy imports
- ❌ Pydantic imports
- ❌ FastAPI imports
- ❌ Any framework dependencies

**Allowed in Domain Layer:**
- ✅ Pure Python dataclasses
- ✅ Standard library (datetime, Decimal, UUID, Enum, abc)
- ✅ Domain Entities with business logic
- ✅ Value Objects (immutable types)
- ✅ Repository Interfaces (ABC protocols)

## 🚀 Tech Stack

- **API Framework:** FastAPI 0.104+
- **ORM:** SQLAlchemy 2.0 (Async)
- **Validation:** Pydantic V2
- **Testing:** Pytest + pytest-asyncio + httpx
- **Database:** PostgreSQL (production) / SQLite (testing)
- **Python:** 3.10+

## 📦 Project Structure

```
Konozy_ai/
├── core/
│   ├── domain/              # Pure Domain Layer
│   │   ├── entities/        # Domain Entities (Order, OrderItem)
│   │   ├── repositories/    # Repository Interfaces (ABC)
│   │   ├── value_objects/   # Value Objects (Money, ExecutionID, OrderNumber)
│   │   └── enums/           # Domain Enums
│   ├── application/         # Application Layer
│   │   ├── services/        # Application Services
│   │   └── dtos/            # Pydantic DTOs
│   └── data/                # Infrastructure Layer
│       ├── models/          # SQLAlchemy ORM Models
│       ├── repositories/    # Repository Implementations
│       ├── mappers.py       # Static Mappers (Domain ↔ DB)
│       └── uow.py           # Unit of Work Pattern
├── apps/
│   └── api/                 # Presentation Layer
│       ├── main.py          # FastAPI Application
│       ├── deps.py          # Dependency Injection
│       └── v1/
│           └── endpoints/   # API Routes
├── tests/
│   └── integration/         # Integration Tests
├── scripts/
│   └── run_architecture_check.sh  # Architecture Validation
└── orchestration/           # Orchestration Layer (Phase 9)
```

## 🔧 Setup & Installation

### Prerequisites

- Python 3.10 or higher
- pip or poetry

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Konozy_ai
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database (optional):**
   
   The default configuration uses PostgreSQL. For testing, SQLite is used automatically.
   
   Update `apps/api/deps.py` with your database URL:
   ```python
   DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"
   ```

## 🏃 Running the Application

### Start the API Server

```bash
# Using uvicorn directly
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# Or using Python
python apps/api/main.py
```

### API Documentation

Once the server is running, access:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

## ✅ Quality Gates

### Architecture Validation

Before committing, always run the architecture validation script:

```bash
./scripts/run_architecture_check.sh
```

**Acceptance Criteria:**
- ✅ Domain purity validated (no SQLAlchemy/Pydantic/FastAPI imports in `core/domain/`)
- ✅ Architecture Violations: **0**
- ✅ All quality gates passed

**If violations > 0, DO NOT COMMIT. Fix all violations first.**

### Running Tests

```bash
# Run all tests
pytest

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage
pytest --cov=core --cov=apps --cov-report=html
```

## 📚 API Endpoints

### Orders API (`/api/v1/orders`)

- **POST /api/v1/orders** - Create a new order
- **GET /api/v1/orders/{order_id}** - Get order by ID
- **GET /api/v1/orders** - List orders with pagination

### Example Request

```bash
curl -X POST "http://localhost:8000/api/v1/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "112-3456789-0123456",
    "purchase_date": "2025-01-13T10:30:00+00:00",
    "buyer_email": "buyer@example.com",
    "items": [
      {
        "sku": "SKU-001",
        "title": "Test Product",
        "quantity": 2,
        "unit_price_amount": "50.00",
        "unit_price_currency": "USD",
        "total_amount": "100.00",
        "total_currency": "USD"
      }
    ],
    "order_status": "Pending"
  }'
```

## 🧪 Testing Strategy

### Integration Tests

Integration tests verify end-to-end functionality:

- API endpoint behavior
- Database persistence
- ExecutionID propagation
- Error handling

Run integration tests:
```bash
pytest tests/integration/ -v
```

## 🏛️ Architectural Principles

### 1. Domain Purity

The domain layer is framework-agnostic and contains only pure business logic.

### 2. Dependency Direction

Dependencies flow **INWARDS** toward the domain:

- Presentation → Application → Domain
- Infrastructure → Domain (implements interfaces)

### 3. Static Mappers

The mapping layer (`core/data/mappers.py`) is the **ONLY** place where domain and infrastructure meet.

- All mapper methods are `@staticmethod`
- Bi-directional conversion (to_domain ↔ to_persistence)
- Handles nested collections recursively

### 4. Unit of Work Pattern

Transaction management via UoW ensures:

- Atomic operations
- ExecutionID propagation
- Clean session lifecycle

## 📝 Development Guidelines

### Adding New Features

1. **Start with Domain Layer:**
   - Define entities and value objects
   - Create repository interfaces
   - Ensure zero framework dependencies

2. **Implement Infrastructure:**
   - Create SQLAlchemy models
   - Implement repository interfaces
   - Add static mappers

3. **Build Application Layer:**
   - Create application services
   - Define DTOs (Pydantic)

4. **Expose via API:**
   - Add endpoints
   - Configure dependency injection
   - Add exception handlers

5. **Test & Validate:**
   - Write integration tests
   - Run architecture validation
   - Ensure Architecture Violations: 0

### Code Quality

- ✅ Type hints on all functions/methods
- ✅ Docstrings for all public interfaces
- ✅ Explicit error handling (no bare `except:`)
- ✅ Follow PEP 8 style guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run architecture validation: `./scripts/run_architecture_check.sh`
5. Run tests: `pytest`
6. Ensure Architecture Violations: **0**
7. Submit a pull request

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

Built with enterprise-grade architectural principles:
- Domain-Driven Design (DDD)
- Hexagonal Architecture (Ports & Adapters)
- Clean Architecture

---

**Remember:** Architecture Violations: **0** or BUST! 🚀
