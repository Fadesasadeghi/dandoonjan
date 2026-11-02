# دندون‌جان | DANDOONJAN

**Persian-first dental evidence intelligence platform**

دندون‌جان یک وب‌اپلیکیشن فارسی برای سازمان‌دهی و تحلیل شواهد مرتبط با پرونده‌های دندان‌پزشکی است. کاربر می‌تواند سؤال خود، توضیحات پرونده و مدارک موجود را ثبت کند و سیستم پیش از تولید گزارش، اطلاعات را به یک مدل ساختاریافته و قابل ردیابی از شواهد تبدیل می‌کند.

> **Evidence → Assessment → Explanation**

دندون‌جان یک چت‌بات تشخیصی یا جایگزین دندان‌پزشک نیست. هدف سیستم کمک به فهم بهتر مدارک، مشخص‌کردن اطلاعات ناقص و آماده‌شدن برای گفت‌وگوی آگاهانه‌تر با دندان‌پزشک است.

## Portfolio Demo

نسخه موجود در این repository برای نمایش فنی و Portfolio آماده شده است و با **داده‌های کاملاً ساختگی** اجرا می‌شود.

در صفحه اصلی می‌توان از گزینه **«مشاهده پرونده نمونه»** استفاده کرد تا workflow پروژه بدون واردکردن اطلاعات واقعی مشاهده شود.

Demo به‌صورت پیش‌فرض از provider آفلاین و deterministic پروژه استفاده می‌کند:

`DJ_AI_PROVIDER=mock`

بنابراین برای اجرای Demo به OpenAI، OpenRouter یا API Key پولی نیاز نیست.

نسخه عمومی Demo تصاویر دندان را واقعاً تفسیر پزشکی نمی‌کند و هیچ خروجی آن نباید به‌عنوان تشخیص، تجویز یا اثبات ضرورت درمان استفاده شود.

## What the project demonstrates

- Persian-first responsive UI with RTL support
- Structured dental case intake
- Evidence and document ingestion
- Treatment and tooth normalization
- Structured extraction from synthetic documents
- Provenance tracking from findings back to source evidence
- Evidence-gap detection
- Assessment and report generation
- Separate patient-facing and professional report views
- Immutable assessment/report snapshots
- Safety gates and fail-closed behavior
- Authentication, session isolation and CSRF protection
- Case ownership boundaries
- Deterministic offline Demo provider
- PDF/report workflow
- Database migrations and PostgreSQL support
- Automated unit, integration, security and regression testing

## Architecture

The central design principle is:

    Files
      ↓
    Ingestion & validation
      ↓
    Structured extraction
      ↓
    Normalized evidence + provenance
      ↓
    Assessment
      ↓
    Immutable snapshot
      ↓
    Patient / professional explanation

Raw uploaded files do not directly become patient-facing answers.

Material findings retain provenance information such as their source artifact and relevant extraction context. Patient-reported, clinician-reported, document-extracted and model-inferred information are kept distinct throughout the workflow.

The project also contains an AI gateway abstraction with deterministic Mock execution for the public Demo and support for a real provider configuration when explicitly enabled.

## Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL / local development database
- Pydantic

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Persian / RTL responsive interface

### Quality & Engineering

- Pytest
- Integration and regression tests
- Security and ingestion tests
- Provenance and snapshot invariants
- Safety evaluation cases
- Versioned prompts, schemas and ontology

## Run locally

Install the project dependencies:

    pip install -r requirements.txt

Create the local environment configuration:

    cp .env.example .env

Start the application:

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config app/logging.json

Then open:

    http://127.0.0.1:8000

No paid AI credentials are required for the default offline Demo.

## Tests

Run the automated test suite with:

    python -m pytest tests -q

The repository includes tests for core workflow behavior, ingestion, authentication and authorization boundaries, provenance, immutable snapshots, safety behavior and regression cases.

## Database migrations

Apply database migrations with:

    alembic upgrade head

## Safety and limitations

This repository is a software engineering and Portfolio project, not a clinically validated medical device.

- All Portfolio Demo data is synthetic.
- Do not enter real patient or sensitive medical information into the public Demo.
- Demo mode does not perform genuine radiographic interpretation.
- Generated explanations are not medical diagnoses.
- Treatment decisions must be made with a qualified dental professional.
- The development Knowledge Pack included in the repository is not clinically validated.

## Engineering documentation

The repository retains its engineering history and technical documentation to demonstrate the development process and architectural decisions.

Additional material is available under:

- `docs/`
- `evaluation/`
- `verification/`

The detailed engineering history and development gates have intentionally been retained as part of the Portfolio repository.

## Project credits

**Software Developer:** Fatemeh Sadeghi — responsible for the design and implementation of the software and its codebase.

**Project Manager:** Mehdi Abbasy — responsible for project management and coordination.

This project was originally developed as a commissioned software project and is published here for Portfolio and technical demonstration purposes with permission.

## Status

**Work in Progress**

DANDOONJAN is under active development. This repository represents the current development state of the project and is published as a portfolio project. Some workflows and deployment-related features are still being completed and refined.
