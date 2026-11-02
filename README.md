<div align="center">

# 🦷 دندون‌جان | DANDOONJAN

### Persian-first Dental Evidence Intelligence Platform

**A structured, safety-oriented platform for organizing dental case evidence, generating traceable assessments, and producing patient-friendly reports.**

<br>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-Frontend-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Work%20in%20Progress-orange?style=for-the-badge)

<br>

**Evidence → Assessment → Explanation**

</div>

---

![DANDOONJAN Landing Page](docs/ui-redesign/reference/aqua-landing-target.png)

---

## About DANDOONJAN

**دندون‌جان** یک وب‌اپلیکیشن فارسی برای سازمان‌دهی و تحلیل شواهد مرتبط با پرونده‌های دندان‌پزشکی است.

کاربر می‌تواند سؤال، توضیحات پرونده و مدارک موجود را ثبت کند. سیستم پیش از تولید گزارش، اطلاعات را پردازش کرده و آن‌ها را به یک مدل ساختاریافته و قابل ردیابی از شواهد تبدیل می‌کند.

هدف اصلی پروژه ایجاد یک workflow قابل‌ردیابی است که مسیر اطلاعات را از **مدرک اولیه** تا **assessment** و در نهایت **توضیح قابل‌فهم برای کاربر** حفظ کند.

> **DANDOONJAN is not a diagnostic chatbot and is not a replacement for a dentist.**

هدف سیستم کمک به سازمان‌دهی و فهم بهتر مدارک، مشخص‌کردن اطلاعات ناقص و آماده‌شدن برای گفت‌وگوی آگاهانه‌تر با متخصص دندان‌پزشکی است.

---

## ✨ Key Features

- 🇮🇷 Persian-first responsive interface with full RTL support
- 🗂️ Structured dental case intake
- 📎 Evidence and document ingestion
- 🦷 Treatment and tooth normalization
- 📄 Structured extraction from synthetic documents
- 🔗 Provenance tracking from findings back to source evidence
- 🔍 Evidence-gap detection
- 🧠 Structured assessment generation
- 👤 Patient-facing report view
- 👩‍⚕️ Professional report view
- 📸 Immutable assessment and report snapshots
- 🔐 Authentication and session isolation
- 🛡️ CSRF protection and case ownership boundaries
- ⚠️ Safety gates and fail-closed behavior
- 🤖 Deterministic offline AI Demo provider
- 📑 PDF and report generation workflow
- 🗄️ Database migrations and PostgreSQL support
- 🧪 Unit, integration, security and regression testing

---

## 🛠️ Tech Stack

### Backend

| Technology | Role |
|---|---|
| **Python 3.11** | Core application language |
| **FastAPI** | Backend API and application framework |
| **Pydantic** | Validation and structured data models |
| **Uvicorn** | ASGI application server |
| **HTTPX** | HTTP client and integration testing |

### Database & Persistence

| Technology | Role |
|---|---|
| **PostgreSQL** | Production-capable relational database |
| **SQLAlchemy** | ORM and persistence layer |
| **Alembic** | Database migrations |
| **psycopg** | PostgreSQL driver |

### Frontend

| Technology | Role |
|---|---|
| **HTML5** | Application structure |
| **CSS3** | Responsive UI and visual system |
| **Vanilla JavaScript** | Client-side application logic |
| **RTL / Persian UI** | Persian-first interface |

### Documents & Media

| Technology | Role |
|---|---|
| **PyMuPDF** | PDF processing |
| **Pillow** | Image processing |
| **python-multipart** | File upload handling |

### Authentication & Security

| Technology | Role |
|---|---|
| **Argon2** | Password hashing |
| **Email Validator** | Email validation |
| **CSRF protection** | Request protection |
| **Session isolation** | User/session boundaries |
| **Ownership checks** | Case-level access boundaries |

### Testing & Engineering

| Technology | Role |
|---|---|
| **Pytest** | Automated testing |
| **HTTPX** | API/integration testing |
| **Alembic migrations** | Schema evolution |
| **Versioned prompts & schemas** | Reproducible AI behavior |
| **Regression tests** | Behavioral preservation |

### Infrastructure

| Technology | Role |
|---|---|
| **Docker** | Containerized runtime |
| **Uvicorn** | Application serving |
| **Environment-based configuration** | Runtime configuration |

---

## 🏗️ Architecture

The central design principle of DANDOONJAN is:

```text
Files
  │
  ▼
Ingestion & Validation
  │
  ▼
Structured Extraction
  │
  ▼
Normalized Evidence + Provenance
  │
  ▼
Assessment
  │
  ▼
Immutable Snapshot
  │
  ▼
Patient / Professional Explanation
```

Raw uploaded files do **not** directly become patient-facing answers.

Material findings retain provenance information such as their source artifact and relevant extraction context.

The system also keeps different information sources conceptually separate, including:

- Patient-reported information
- Clinician-reported information
- Document-extracted information
- Model-inferred information

This separation is maintained throughout the workflow to make the resulting assessment more traceable and auditable.

---

## 🤖 AI Architecture

DANDOONJAN contains an AI gateway abstraction designed to separate the application workflow from the underlying AI provider.

For the public Portfolio Demo, the project uses a deterministic offline provider:

```env
DJ_AI_PROVIDER=mock
```

This allows the Demo workflow to run without requiring paid AI credentials.

The architecture also supports configuration for a real provider when explicitly enabled.

The public Demo does **not** perform genuine medical interpretation of dental radiographs.

---

## 🎮 Portfolio Demo

The version published in this repository is intended for technical demonstration and Portfolio use.

All Demo data is **synthetic**.

The landing page includes the option:

> **مشاهده پرونده نمونه**

which allows the application workflow to be explored without entering real patient information.

No OpenAI, OpenRouter or other paid API key is required for the default offline Demo configuration.

---

## 🛡️ Safety by Design

Because DANDOONJAN works with dental evidence and medical-adjacent information, safety boundaries are part of the application architecture rather than an afterthought.

The project includes:

- Safety gates
- Fail-closed behavior
- Evidence provenance
- Evidence-gap detection
- Immutable assessment snapshots
- Separation of reported, extracted and inferred information
- Authentication and authorization boundaries
- Synthetic Portfolio Demo data
- Explicit limitations around medical interpretation

### Important limitation

This repository is a **software engineering and Portfolio project**, not a clinically validated medical device.

The generated information must not be interpreted as a medical diagnosis, prescription or proof that a particular treatment is required.

Treatment decisions must be made with a qualified dental professional.

---

## 🚀 Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/Fadesasadeghi/dandoonjan.git
cd dandoonjan
```

### 2. Create a virtual environment

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the environment configuration

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

### 5. Start the application

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config app/logging.json
```

Then open:

```text
http://127.0.0.1:8000
```

The default offline Demo does not require paid AI credentials.

---

## 🧪 Tests

Run the automated test suite:

```bash
python -m pytest tests -q
```

The repository contains automated coverage for areas including:

- Core workflow behavior
- Evidence ingestion
- Authentication
- Authorization boundaries
- Provenance
- Immutable snapshots
- Safety behavior
- Integration behavior
- Regression cases

---

## 🗄️ Database Migrations

Apply the available database migrations with:

```bash
alembic upgrade head
```

---

## 📚 Engineering Documentation

DANDOONJAN retains a significant portion of its engineering documentation and development history.

This is intentional.

The repository documents not only the resulting application but also parts of the engineering process used to build and validate it.

Additional technical material is available under:

```text
docs/
evaluation/
verification/
```

These materials include architectural decisions, testing records, safety considerations, UI development evidence and development gates.

---

## ⚠️ Safety & Limitations

Please keep the following limitations in mind:

- All Portfolio Demo data is synthetic.
- Do not enter real patient or sensitive medical information into the public Demo.
- Demo mode does not perform genuine radiographic interpretation.
- Generated explanations are not medical diagnoses.
- Generated output must not be used as proof of treatment necessity.
- Treatment decisions must be made with a qualified dental professional.
- The development Knowledge Pack included in the repository is not clinically validated.
- Some workflows and deployment-related functionality remain under development.

---

## 👩‍💻 Project Credits

### Software Developer

**Fatemeh Sadeghi**

Responsible for the design and implementation of the software and its codebase, including application development, architecture implementation, frontend and backend development, testing and technical refinement.

### Project Manager

**Mehdi Abbasy**

Responsible for project management and coordination.

---

This project was originally developed as a commissioned software project and is published here for **Portfolio and technical demonstration purposes with permission**.

---

## 🚧 Project Status

> **Work in Progress**

DANDOONJAN is under active development.

This repository represents the current development state of the project and is published as a Portfolio project. Some workflows and deployment-related features are still being completed and refined.

---

<div align="center">

### 🦷 DANDOONJAN

**Structured evidence. Traceable assessment. Clearer explanation.**

Built with Python, FastAPI and a safety-oriented engineering approach.

</div>
