# Gemini API Integration Guide

Your UmojaFunds SACCO ERP system is now equipped with **Gemini AI integration** to power intelligent features across the platform. This guide will help you connect the Gemini API and unlock advanced AI capabilities.

## 🎯 Features Powered by Gemini

Once connected, Gemini AI enhances your SACCO ERP with:

### 1. **AI Assistant (Chat Interface)**
- Natural language queries about your SACCO operations
- Real-time portfolio analysis and recommendations
- Context-aware responses using your actual member, loan, and transaction data
- Multi-turn conversations with full context retention

### 2. **Intelligent Loan Analysis**
- AI-powered loan application assessment
- Risk scoring with detailed explanations
- Personalized recommendations for approval/rejection
- Suggested interest rates and loan terms

### 3. **Fraud Detection**
- Pattern recognition across transactions
- Anomaly explanation and risk assessment
- Proactive fraud prevention recommendations

### 4. **Collections Optimization**
- Personalized payment reminder generation
- Tone-adaptive messaging (formal/friendly/urgent)
- Multi-variant reminder creation for A/B testing

### 5. **Financial Forecasting**
- AI-driven savings and loan projections
- NPL ratio trend predictions
- Seasonality detection and planning recommendations

### 6. **Member Churn Analysis**
- At-risk member identification
- Retention strategy recommendations
- Product development suggestions

---

## 🚀 Quick Setup (3 Minutes)

### Step 1: Get Your Gemini API Key

1. Visit [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account (or create one)
3. Click **"Get API key"**
4. Copy your API key

### Step 2: Connect to UmojaFunds

#### Option A: Through the UI (Recommended)
1. Navigate to **AI Assistant** in the sidebar
2. Click the **"Connect Gemini"** button in the header
3. Paste your API key in the modal
4. Click **"Connect Gemini"**
5. ✅ You're ready! The chat interface will confirm connection

#### Option B: Browser Console
Open your browser's developer console and run:
```javascript
localStorage.setItem('GEMINI_API_KEY', 'YOUR-GEMINI-API-KEY-HERE');
```
Then refresh the page.

### Step 3: Test the Connection

Try asking the AI Assistant:
- "Show me members at risk of defaulting"
- "What's the current NPL ratio and how does it compare to SASRA standards?"
- "Generate a friendly payment reminder for overdue loans"
- "Forecast loan repayments for next quarter"

---

## 📊 Gemini API Usage & Costs

### Model Used
- **Model:** `gemini-1.5-pro`
- **Max Tokens:** 8,192 per response
- **Context Window:** Full SACCO data included in system prompt

### Pricing (as of 2024)
- **Input:** ~$0.125 per million tokens
- **Output:** ~$0.375 per million tokens

### Estimated Costs
For typical SACCO admin usage:
- **Light use** (10-20 queries/day): ~$1-3/month
- **Moderate use** (50-100 queries/day): ~$5-15/month
- **Heavy use** (200+ queries/day): ~$20-60/month

💡 **Tip:** Each query includes your full SACCO context (~1-2K tokens), so costs scale with usage frequency.

---

## 🔒 Security & Privacy

### Data Handling
- **API Key Storage:** Stored locally in browser's `localStorage` (never sent to our servers)
- **Data Transmission:** SACCO data is sent to Google's API for each query
- **Encryption:** All API calls use HTTPS/TLS encryption
- **Retention:** Google does NOT train models on your API data (per their policy)

### ⚠️ Important Security Notes

#### Development vs Production
This implementation uses **client-side API calls** which exposes your API key in the browser. This is acceptable for:
- ✅ Development and testing
- ✅ Internal admin tools (trusted users only)
- ✅ Proof-of-concept deployments

For production deployment with external users:
- ❌ **DO NOT** use client-side API calls
- ✅ **DO** route through a backend proxy
- ✅ **DO** implement rate limiting
- ✅ **DO** add authentication/authorization

#### Recommended Production Architecture
```
[Browser] → [Your Backend API] → [Gemini API]
   ↑              ↑                    ↑
 User UI    Auth + Rate Limit    API Key (secure)
```

### Data Privacy Checklist
- [ ] Ensure your Google account has appropriate data handling agreements
- [ ] Review Google's [privacy policy](https://policies.google.com/privacy)
- [ ] Confirm compliance with your local data protection regulations (GDPR, etc.)
- [ ] If handling sensitive member data, consider anonymization before sending to Gemini
- [ ] Implement audit logging for AI queries in production

---

## 🛠️ Troubleshooting

### "Invalid API key" Error
**Problem:** API key format is incorrect or expired
**Solution:** 
- Verify key follows Gemini API key format
- Regenerate key at makersuite.google.com
- Clear localStorage: `localStorage.removeItem('GEMINI_API_KEY')`

### "Rate limit exceeded" Error
**Problem:** Too many requests in short time
**Solution:**
- Wait 60 seconds before retrying
- Upgrade your Google AI plan for higher limits
- Implement request queuing in production

### Slow Responses
**Problem:** Gemini API taking 5-10 seconds to respond
**Solution:**
- This is normal for complex queries with full context
- Consider reducing context size for faster responses
- Show loading indicators to improve UX

### Fallback to Mock Responses
**Problem:** Gemini API fails but app still works
**Solution:**
- ✅ This is intentional! The app gracefully falls back to rule-based responses
- Check browser console for detailed error messages
- Verify internet connection and API key validity

---

## 🎨 Customization

### Adjust Response Length
Edit `/src/services/gemini.ts`:
```typescript
const result = await model.generateContent(prompt, {
  maxOutputTokens: 2048, // ← Change this (1-8192)
});
```

### Change AI Model
```typescript
model: "gemini-1.5-pro", // Premium, best quality
// or
model: "gemini-1.5-flash",   // Faster, cheaper
```

### Customize System Prompt
The system prompt in `buildSaccoContext()` tells Gemini how to behave. Modify it to:
- Change tone (more formal, more casual)
- Add domain-specific knowledge
- Enforce output formats (JSON, tables, etc.)

### Add Custom AI Functions
See `/src/services/gemini.ts` for examples:
- `analyzeLoanApplication()` - Loan assessment
- `detectFraudPatterns()` - Fraud analysis
- `generateCollectionReminder()` - SMS generation
- `getFinancialForecast()` - Forecasting

Create your own following the same pattern!

---

## 📈 Monitoring & Analytics

### Track API Usage
Monitor your usage at: [makersuite.google.com/usage](https://makersuite.google.com/usage)

### Key Metrics to Watch
- **Request volume:** Queries per day/week
- **Token usage:** Input vs output token ratio
- **Error rate:** Failed requests / total requests
- **Latency:** Average response time

### Cost Optimization Tips
1. **Cache frequent queries:** Store common responses locally
2. **Reduce context size:** Only send relevant member/loan data
3. **Batch requests:** Combine multiple questions when possible
4. **Use cheaper models:** Switch to gemini-1.5-flash for simple queries
5. **Implement rate limiting:** Prevent accidental runaway costs

---

## 🔄 Updating the Integration

### Update Google AI SDK
```bash
npm update @google/generative-ai
```

### Switch Models
When new Gemini models release, update the model name in `/src/services/gemini.ts`:
```typescript
model: "gemini-1.5-pro-YYYYMMDD", // Use latest version
```

### Remove Gemini Integration
To disable Gemini and revert to mock responses:
1. Remove API key: `localStorage.removeItem('GEMINI_API_KEY')`
2. Refresh the page
3. App will function with rule-based responses

---

## 💬 Support & Resources

### Google Documentation
- [API Reference](https://ai.google.dev/api)
- [Prompt Engineering](https://ai.google.dev/gemini-api/docs/prompting)
- [Model Comparison](https://ai.google.dev/gemini-api/docs/models)

### UmojaFunds AI Code
- **Service Module:** `/src/services/gemini.ts`
- **AI Assistant:** `/src/app/App.tsx` (AIAssistantView component)
- **Integration Points:** Search for `sendGeminiMessage` in codebase

### Common Questions

**Q: Can I use this offline?**
A: No, Gemini API requires internet connection. Fallback mock responses work offline.

**Q: Is there a free tier?**
A: Google AI Studio offers a free tier with generous limits. Check their pricing page.

**Q: Can I use multiple API keys?**
A: Currently one key per browser. Implement key rotation in the backend for production.

**Q: How do I reset the chat?**
A: Refresh the page or click the AI Assistant menu item again.

**Q: Can I export chat history?**
A: Not currently implemented. Add export feature by accessing the `messages` state.

---

## ✅ Next Steps

Now that Gemini is connected, explore these advanced features:

1. **Test Different Queries:**
   - Financial forecasting
   - Member risk analysis
   - Fraud pattern detection

2. **Integrate into Workflows:**
   - Use AI Loan Scoring before approvals
   - Generate collection reminders automatically
   - Monitor fraud alerts daily

3. **Customize for Your SACCO:**
   - Adjust system prompts for your policies
   - Add custom AI functions for specific needs
   - Fine-tune response formats

4. **Plan for Production:**
   - Set up backend proxy
   - Implement rate limiting
   - Add audit logging
   - Configure budget alerts

---

## 🎉 Congratulations! 
Your SACCO ERP is now AI-powered with Gemini. Enjoy intelligent insights and automation! 🚀

---

*Last updated: 2024*
*Google AI SDK Version: 0.12.0*
*Gemini Model: gemini-1.5-pro*