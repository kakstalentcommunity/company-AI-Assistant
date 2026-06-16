# UmojaFunds SACCO ERP System

A comprehensive **Savings and Credit Cooperative Organization (SACCO) Management System** with AI-powered insights, built with a **Python/FastAPI** backend and a **React/TypeScript** frontend.

---

## Overview

UmojaFunds helps SACCOs manage core operations — member management, savings, loans, transactions, and financial reporting — with integrated AI for decision-making, fraud detection, loan scoring, and predictive analytics.

The system serves **East African SACCOs** regulated by **SASRA** (Sacco Societies Regulatory Authority) and integrates with **M-Pesa** for mobile money transactions.

---

## Architecture

```
SaccoERP/
├── backend/          # Python / FastAPI REST API
│   ├── app/
│   │   ├── routes/       # API endpoint definitions
│   │   ├── services/     # Business logic (member intelligence, AI queries)
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── config.py     # Application configuration
│   │   └── security.py   # Auth (Bearer tokens, session management)
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # React / Vite / TypeScript UI
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

### Backend (`backend/`)
- **Framework**: FastAPI
- **ORM**: SQLAlchemy (SQLite for dev, MySQL for production)
- **Auth**: JWT-based (Bearer tokens with idle timeout)
- **AI**: Gemini API via function-calling for natural-language database queries

### Frontend (`frontend/`)
- **Framework**: React 18+ with TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS + Radix UI + Lucide Icons
- **Charts**: Recharts

---

## Key Features

### Core SACCO Operations
- **Member Management** — profiles, savings, shares, status tracking
- **Loan Portfolio** — disbursement, repayment schedules, overdue tracking
- **Savings Accounts** — FOSA accounts, deposits, withdrawals
- **Transaction Processing** — deposits, withdrawals, transfers, checkoff
- **Financial Reporting** — dashboards, portfolio summaries, NPL ratios

### AI-Powered Capabilities
- **AI Assistant (UmojaAI)** — ask questions in natural language; the AI calls database tools to answer with real data
- **Loan Scoring** — AI-driven credit risk assessment
- **Fraud Detection** — anomaly detection in transactions
- **Collections Intelligence** — reminder generation, risk prioritization
- **Financial Forecasting** — predictions for savings, loans, and cash flow
- **Member Analytics** — churn prediction, retention recommendations

### External MySQL Tables Queryable via AI
The AI assistant can search **100+ external MySQL tables** by any searchable column. Users simply ask questions like:
- *"Show me fixed deposits"* → queries `cr_fixed_deposits`
- *"Find employer UMOJA"* → queries `cr_employers`
- *"List dividend withdrawal charges"* → queries `cr_dividend_withdrawal_charges`
- *"How many loans are outstanding?"* → portfolio summary

---

## Getting Started

### Prerequisites
- Python 3.14+
- Node.js 18+ and npm / pnpm
- MySQL (production) or SQLite (development)
- Gemini API key (for AI assistant)

### Backend Setup

```bash
# Clone the repository
git clone <repository-url>
cd SaccoERP

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
cd backend
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and Gemini API key

# Run the server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm run dev
```

The API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./umojafunds.sqlite3` |
| `MYSQL_HOST` | External MySQL host | — |
| `MYSQL_PORT` | External MySQL port | `3306` |
| `MYSQL_USER` | MySQL user | — |
| `MYSQL_PASSWORD` | MySQL password | — |
| `MYSQL_DATABASE` | MySQL database name | — |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `SECRET_KEY` | JWT signing secret | — |
| `SESSION_IDLE_MINUTES` | Session timeout | `30` |

---

## Contributing

See [`frontend/CONTRIBUTING.md`](frontend/CONTRIBUTING.md) and [`frontend/ARCHITECTURE.md`](frontend/ARCHITECTURE.md) for detailed contribution guidelines and architecture documentation.

---

## License

This project is licensed under the terms included in the [`LICENSE`](frontend/LICENSE) file.