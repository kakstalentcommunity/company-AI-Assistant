# UmojaFunds SACCO ERP System

A comprehensive Savings and Credit Cooperative Organization (SACCO) Management System with AI-powered insights, built with a Python/FastAPI backend and a React/TypeScript frontend.

## Overview

UmojaFunds is designed to help SACCOs manage their core operations including member management, savings, loans, transactions, and financial reporting. The system integrates AI capabilities for enhanced decision-making, fraud detection, loan scoring, and predictive analytics.

## Architecture

The system consists of two main components:

### Backend (Python/FastAPI)
- **Location**: `backend/` directory
- **Responsibilities**: 
  - RESTful API for all business logic
  - Data persistence with SQLAlchemy ORM (SQLite/MySQL)
  - Authentication and authorization
  - AI integration (via external API calls to Gemin)
  - Product usage analytics and event tracking
  - Admin functions and audit logging

### Frontend (React/Vite)
- **Location**: `Apipoweredsaccoerp/` directory
- **Responsibilities**:
  - User interface for SACCO staff and members
  - Real-time data visualization with charts
  - AI assistant for natural language queries
  - Responsive design for desktop and mobile
  - Product usage tracking (frontend to backend)

## Key Features

### Core SACCO Functionality
- Member management (profiles, savings, shares, status)
- Loan portfolio management (disbursement, repayments, tracking)
- Savings account management
- Transaction processing (deposits, withdrawals, transfers)
- Financial reporting and dashboards
- Membership and loan application workflows

### AI-Powered Capabilities
- **AI Assistant**: Natural language interface for querying SACCO data
- **Loan Scoring**: AI-driven credit risk assessment using multiple factors
- **Fraud Detection**: Anomaly detection in transactions using machine learning
- **Collections Intelligence**: Personalized reminder generation and risk prioritization
- **Financial Forecasting**: AI predictions for savings, loans, and cash flow
- **Member Analytics**: Churn prediction and retention strategy recommendations

### Technical Features
- Role-based access control (admin, staff, member)
- Comprehensive audit logging
- Intrusion detection event logging for suspicious API activity
- RESTful API with detailed OpenAPI/Swagger documentation
- Real-time data synchronization
- Secure authentication (JWT-based)
- Environment-based configuration
- Docker-ready for containerization

## Technology Stack

### Backend
- **Language**: Python 3.14+
- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Database**: SQLite (development) / MySQL (production)
- **Authentication**: Python-JOSE (JWT)
- **AI Integration**: Anthropic Claude API
- **Other**: Pydantic, Python-dotenv

### Frontend
- **Language**: TypeScript
- **Framework**: React 18+
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI, Lucide Icons
- **Data Visualization**: Recharts
- **State Management**: React Context/Hooks
- **AI Integration**: Anthropic Claude SDK

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.14+
- Git
- (Optional) Docker and Docker Compose

### Backend Setup
```bash
# Clone the repository
git clone <repository-url>
cd apipo/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize the database
python -m app.database.init_db

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd ../Apipoweredsaccoerp

# Install dependencies
npm install

# Set up environment variables (if needed)
# The frontend proxies API requests to backend via vite.config.ts

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173` and will proxy API requests to `http://localhost:8000`.

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Frontend Documentation

See the frontend's README for detailed information:
- `Apipoweredsaccoerp/README.md` - Focuses on Claude AI integration
- `Apipoweredsaccoerp/src/services/README.md` - API service documentation

## Backend Documentation

- `backend/app/docs/product_usage_analytics.md` - Product analytics schema and API
- `backend/app/docs/intrusion_detection.md` - IDS event logging, schema, admin endpoints, and configuration
- Inline documentation in the codebase (docstrings and comments)

## Environment Configuration

### Backend (.env)
```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=123456
DB_NAME=umoja_funds
ENVIRONMENT=development

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
IDS_ENABLED=true
IDS_DETAIL_MAX_LENGTH=2000
MAX_REQUEST_BYTES=1000000

# CORS
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
TRUSTED_HOSTS=localhost,127.0.0.1,*.localhost

# AI Integration (Claude)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Email (for notifications)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
```

### Frontend
The frontend uses Vite's proxy configuration in `vite.config.ts` to forward `/api` requests to the backend. No additional environment variables are required for basic operation.

## Deployment

### Production Considerations
1. Use a production-ready ASGI server (e.g., Gunicorn with Uvicorn workers)
2. Configure a reverse proxy (Nginx) for SSL termination
3. Use environment-specific configuration files
4. Set up logging and monitoring
5. Implement regular database backups
6. Use a managed database service (AWS RDS, Google Cloud SQL, etc.)

### Docker Deployment
The project can be containerized using Docker. Example `docker-compose.yml`:

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend/data:/app/data
  frontend:
    build: ./Apipoweredsaccoerp
    ports:
      - "5173:5173"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

Please ensure your code follows the existing style and includes appropriate tests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Frontend powered by [React](https://reactjs.org/) and [Vite](https://vitejs.dev/)
- AI capabilities provided by [Anthropic Claude](https://www.anthropic.com/)
- Icons from [Lucide](https://lucide.dev/)
- Charts powered by [Recharts](https://recharts.org/)
- UI components from [Radix UI](https://www.radix-ui.com/)

---
*Last updated: June 2026*
