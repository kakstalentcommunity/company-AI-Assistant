# UmojaFunds SACCO ERP - Claude AI Architecture

## 🏗️ System Architecture

### Current Implementation (Development Mode)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Browser / User Device                        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    React Application                       │ │
│  │                     (App.tsx)                             │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │         UI Components & Views                       │ │ │
│  │  │                                                      │ │ │
│  │  │  • Dashboard                                        │ │ │
│  │  │  • AI Assistant (Chat Interface)                   │ │ │
│  │  │  • Loan Scoring                                    │ │ │
│  │  │  • Fraud Detection                                 │ │ │
│  │  │  • Collections                                     │ │ │
│  │  │  • Members, Loans, Transactions                   │ │ │
│  │  │                                                      │ │ │
│  │  └──────────────────┬───────────────────────────────────┘ │ │
│  │                     │                                       │ │
│  │                     ▼                                       │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │         Claude Service Module                        │ │ │
│  │  │        (src/services/claude.ts)                     │ │ │
│  │  │                                                      │ │ │
│  │  │  • sendClaudeMessage()                              │ │ │
│  │  │  • analyzeLoanApplication()                         │ │ │
│  │  │  • detectFraudPatterns()                           │ │ │
│  │  │  • generateCollectionReminder()                    │ │ │
│  │  │  • getFinancialForecast()                          │ │ │
│  │  │  • buildSaccoContext()                             │ │ │
│  │  │                                                      │ │ │
│  │  └──────────────────┬───────────────────────────────────┘ │ │
│  │                     │                                       │ │
│  └─────────────────────┼───────────────────────────────────────┘ │
│                        │                                         │
│         ┌──────────────┴──────────────┐                         │
│         │    localStorage              │                         │
│         │  Gemini_API_KEY          │                         │
│         │  Gemini_banner_dismissed    │                         │
│         └─────────────────────────────┘                         │
│                        │                                         │
└────────────────────────┼─────────────────────────────────────────┘
                         │
                         │ HTTPS / TLS
                         │ (dangerouslyAllowBrowser: true)
                         ▼
              ┌──────────────────────┐
              │  Gemini API      │
              │  (Gemini AI)         │
              │                      │
              │  claude-3-5-sonnet   │
              │  max_tokens: 2048    │
              └──────────────────────┘
```

---

## 🔄 Data Flow

### 1. User Query Flow

```
User types query
    │
    ▼
AIAssistantView.send()
    │
    ├─► Check if claudeEnabled
    │   │
    │   ├─► NO → Show API key modal
    │   │
    │   └─► YES → Continue
    │
    ├─► Add user message to UI
    │
    ├─► Build SACCO context
    │       • Members data
    │       • Loans data
    │       • Transactions data
    │       • Portfolio data
    │       • Member profiles
    │
    ├─► Prepare conversation history
    │
    ▼
sendClaudeMessage(query, context, history)
    │
    ├─► getClient() → Initialize Anthropic SDK
    │
    ├─► buildSaccoContext(context) → Create system prompt
    │       ├─► Calculate member statistics
    │       ├─► Summarize loan portfolio
    │       ├─► Analyze transactions
    │       └─► Add SASRA/Kenyan context
    │
    ├─► Call Claude API
    │       POST https://api.anthropic.com/v1/messages
    │       {
    │         model: "claude-3-5-sonnet-20241022",
    │         max_tokens: 2048,
    │         system: systemPrompt,
    │         messages: [history + userQuery]
    │       }
    │
    ├─► Receive response
    │   │
    │   ├─► Success → Return AI response
    │   │
    │   └─► Error → Throw error
    │
    ▼
AIAssistantView.send() continues
    │
    ├─► SUCCESS
    │   └─► Add AI response to chat
    │
    └─► ERROR
        ├─► Display error message
        └─► Fall back to mock response (getAIResponse)
```

---

## 🔑 API Key Management

### Storage Flow

```
User enters API key
    │
    ▼
Validation
    ├─► Check if starts with "sk-ant-"
    │
    ├─► Empty check
    │
    ▼
localStorage.setItem('ANTHROPIC_API_KEY', key)
    │
    ▼
resetClaudeClient()  (Clear cached client)
    │
    ▼
Update UI
    ├─► Set claudeEnabled = true
    ├─► Update header status
    ├─► Update AI capabilities panel
    └─► Hide connection banner
```

### Retrieval Flow

```
isClaudeConfigured()
    │
    ▼
localStorage.getItem('ANTHROPIC_API_KEY')
    │
    ├─► Found → return true
    │
    └─► Not found → return false

───────────────────────────────

getClient()
    │
    ├─► Client cached? → Return cached
    │
    └─► No cache:
        │
        ├─► Get key from localStorage
        │
        ├─► No key? → Throw error
        │
        └─► Create new Anthropic client
            │
            └─► Cache for future use
```

---

## 🎯 Component Hierarchy

```
App (Main Component)
│
├─► Sidebar
│   └─► Navigation items (including AI modules)
│
├─► Header
│   ├─► Page title
│   ├─► Claude badge (if AI module)
│   └─► User profile
│
├─► Claude Connection Banner (conditional)
│   ├─► Dismiss button
│   └─► "Connect Claude" CTA
│
└─► Main Content (renderView)
    │
    ├─► DashboardView
    ├─► MembersView
    ├─► LoansView
    ├─► TransactionsView
    ├─► ReportsView
    │
    ├─► AIAssistantView ← Claude Integration
    │   │
    │   ├─► Chat Header
    │   │   ├─► Bot avatar
    │   │   ├─► Status indicator
    │   │   └─► "Connect Claude" button
    │   │
    │   ├─► Messages Container
    │   │   ├─► Message bubbles
    │   │   ├─► Typing indicator
    │   │   └─► Scroll anchor
    │   │
    │   ├─► Suggested Prompts
    │   │
    │   ├─► Error Display (conditional)
    │   │
    │   ├─► Input Form
    │   │
    │   ├─► API Key Modal (conditional)
    │   │   ├─► Instructions
    │   │   ├─► API key input
    │   │   ├─► Security warning
    │   │   └─► Connect button
    │   │
    │   └─► Right Panel
    │       ├─► AI Capabilities card
    │       ├─► Forecast chart
    │       └─► High-risk members
    │
    ├─► LoanScoringView ← Uses Claude
    ├─► FraudDetectionView ← Uses Claude
    └─► CollectionsView ← Uses Claude
```

---

## 🌐 Network Architecture

### Current (Development)

```
┌─────────────┐
│   Browser   │
│             │
│  React App  │
│     +       │
│  API Key    │
└──────┬──────┘
       │
       │ Direct HTTPS
       │ (Client-side call)
       ▼
┌─────────────┐
│  Anthropic  │
│   API       │
│             │
│   Claude    │
└─────────────┘
```

**Security Level:** ⚠️ Development only
**Risk:** API key exposed in browser
**Suitable for:** Testing, internal tools, demos

---

### Recommended (Production)

```
┌─────────────┐
│   Browser   │
│             │
│  React App  │
│ (No API Key)│
└──────┬──────┘
       │
       │ HTTPS
       │ Auth Token
       ▼
┌─────────────┐
│   Backend   │
│   Proxy     │
│             │
│  Features:  │
│  • Auth     │
│  • Rate Limit
│  • Logging  │
│  • API Key  │
│    (secure) │
└──────┬──────┘
       │
       │ HTTPS
       │ (Server-side)
       ▼
┌─────────────┐
│  Anthropic  │
│   API       │
│             │
│   Claude    │
└─────────────┘
```

**Security Level:** ✅ Production-ready
**Risk:** Minimal
**Suitable for:** Public apps, external users

---

## 📦 Module Dependencies

```
App.tsx
  │
  ├─► React (UI framework)
  ├─► Lucide Icons (Bot, Key, Sparkles, etc.)
  ├─► Recharts (Data visualization)
  │
  └─► src/services/claude.ts
        │
        ├─► @anthropic-ai/sdk (Claude client)
        │
        └─► Browser APIs
              ├─► localStorage (API key storage)
              ├─► fetch (HTTP calls via SDK)
              └─► Date (Timestamp formatting)
```

---

## 🔒 Security Boundaries

### Trust Boundaries

```
┌────────────────────────────────────────────────┐
│           TRUSTED                              │
│                                                │
│  • React Application Code                     │
│  • Service Module (claude.ts)                 │
│  • UI Components                              │
│                                                │
└─────────────────┬──────────────────────────────┘
                  │
    ══════════════╪══════════════════
                  │ localStorage
                  │ (Semi-trusted)
    ══════════════╪══════════════════
                  │
┌─────────────────┴──────────────────────────────┐
│           EXTERNAL / UNTRUSTED                 │
│                                                │
│  • User Input (Chat queries)                  │
│  • Anthropic API (External service)           │
│  • Network Layer                              │
│                                                │
└────────────────────────────────────────────────┘
```

### Data Classification

| Data Type | Sensitivity | Where Stored | Sent to Claude? |
|-----------|-------------|--------------|-----------------|
| API Key | 🔴 Critical | localStorage | No (used for auth) |
| Member Data | 🟡 Sensitive | React state | Yes (in context) |
| Loan Data | 🟡 Sensitive | React state | Yes (in context) |
| Transaction Data | 🟡 Sensitive | React state | Yes (in context) |
| Chat Messages | 🟢 Low | React state | Yes (conversation) |
| UI State | 🟢 Low | React state | No |

---

## ⚡ Performance Architecture

### Caching Strategy

```
Request Flow:

User Query
    │
    ├─► Check Anthropic Client Cache
    │   │
    │   ├─► Cached → Use existing client
    │   │
    │   └─► Not cached → Create new, cache it
    │
    ├─► Build context (no cache)
    │
    ├─► API Call to Claude
    │
    └─► Display response (no cache)
```

**What's Cached:**
- ✅ Anthropic client instance (until page refresh)

**What's NOT Cached:**
- ❌ API responses (always fresh)
- ❌ SACCO context (rebuilt each query)
- ❌ Conversation history (only in React state)

### Optimization Opportunities

```
Future Enhancements:

1. Response Caching
   • Cache common queries (e.g., "NPL ratio")
   • Invalidate after data changes
   • Reduce API calls by 30-50%

2. Context Optimization
   • Send only relevant data (not full dataset)
   • Filter members/loans based on query
   • Reduce token usage by 40-60%

3. Debouncing
   • Delay send on rapid typing
   • Cancel in-flight requests
   • Improve UX and reduce costs

4. Streaming Responses
   • Use Claude's streaming API
   • Show response word-by-word
   • Improve perceived performance
```

---

## 🎯 Integration Points

### Where Claude is Used

```
1. AI Assistant View
   ├─► sendClaudeMessage() → General queries
   └─► Full conversation context

2. Loan Scoring View (Future)
   └─► analyzeLoanApplication() → Credit assessment

3. Fraud Detection View (Future)
   └─► detectFraudPatterns() → Anomaly analysis

4. Collections View (Future)
   └─► generateCollectionReminder() → SMS generation

5. Dashboard (Future)
   ├─► getFinancialForecast() → Projections
   └─► analyzeMemberChurn() → Retention insights
```

### Extensibility Points

Add new AI features by:

1. Create function in `/src/services/claude.ts`
2. Import in component
3. Call with appropriate context
4. Handle response in UI

Example:
```typescript
// In claude.ts
export async function analyzePortfolioRisk(saccoContext) {
  return sendClaudeMessage(
    "Analyze portfolio risk and recommend actions",
    saccoContext
  );
}

// In component
const riskReport = await analyzePortfolioRisk({ loans, members });
```

---

## 📊 Monitoring Architecture

### What to Monitor

```
┌────────────────────────────────────────────┐
│         Application Layer                  │
│                                            │
│  • Error rate (catch blocks)              │
│  • Response times (send → receive)        │
│  • Fallback usage (mock vs Claude)       │
│  • User engagement (queries/session)      │
│                                            │
└─────────────────┬──────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────┐
│         API Layer                          │
│                                            │
│  • Request count (per hour/day)           │
│  • Token usage (input + output)           │
│  • Cost tracking ($ spent)                │
│  • Rate limit hits                        │
│                                            │
│  ► Monitor at: console.anthropic.com      │
│                                            │
└────────────────────────────────────────────┘
```

---

## 🚀 Deployment Architecture

### Development
```
Local Machine → npm run dev → Browser
                               ↓
                           Claude API
```

### Staging (Recommended)
```
Staging Server → Build → CDN/Static Host → Browser
                                             ↓
                                    Backend Proxy → Claude API
```

### Production (Recommended)
```
Production Server → Build → CDN → Browser
                                    ↓
                              Load Balancer
                                    ↓
                              Backend Cluster → Claude API
                              (Auth, Rate Limit,
                               Logging, Caching)
```

---

## 📚 Documentation Architecture

```
/
├── README.md ─────────────────► Overview & Quick Links
│
├── GETTING_STARTED_CLAUDE.md ─► 3-minute setup guide
│
├── CLAUDE_API_SETUP.md ───────► Comprehensive guide
│
├── QUICK_REFERENCE.md ────────► Cheat sheet
│
├── INTEGRATION_CHECKLIST.md ─► Verification tests
│
├── ARCHITECTURE.md ───────────► This file
│
└── src/services/
    └── README.md ─────────────► Developer API docs
```

Each doc serves a specific audience:
- **End Users:** GETTING_STARTED, QUICK_REFERENCE
- **Admins:** CLAUDE_API_SETUP, INTEGRATION_CHECKLIST
- **Developers:** src/services/README, ARCHITECTURE

---

**Architecture designed for:**
- ✅ Rapid development
- ✅ Easy deployment
- ✅ Clear upgrade path
- ✅ Security awareness
- ✅ Cost transparency
- ✅ Future extensibility

---

*Last updated: 2024*
*Version: 2.0 (Claude Integration)*
