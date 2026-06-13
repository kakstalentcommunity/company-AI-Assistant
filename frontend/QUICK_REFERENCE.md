# Claude API Quick Reference Card

## 🔑 Setup (30 seconds)
```javascript
// In browser console or use the UI button
localStorage.setItem('ANTHROPIC_API_KEY', 'sk-ant-api03-YOUR-KEY-HERE');
```
Then refresh the page.

## ✅ Verify Connection
```javascript
localStorage.getItem('ANTHROPIC_API_KEY')  // Should show your key
```

## 🗑️ Disconnect
```javascript
localStorage.removeItem('ANTHROPIC_API_KEY');  // Remove key
localStorage.setItem('claude_banner_dismissed', 'false');  // Reset banner
```
Then refresh the page.

## 💬 Sample Queries to Try

### Portfolio Analysis
```
"What's the current NPL ratio and how does it compare to SASRA standards?"
"Show me a breakdown of loan portfolio by type and risk level"
"Which members have the highest credit risk?"
```

### Loan Decisions
```
"Should we approve a KES 500K loan for Amara Okonkwo?"
"Analyze Kofi Mensah's creditworthiness for a new loan"
"What interest rate should we offer for education loans?"
```

### Fraud Detection
```
"Are there any suspicious transaction patterns in the last 7 days?"
"Explain why TXN-884919 was flagged"
"What fraud prevention measures should we implement?"
```

### Collections
```
"Generate a friendly payment reminder for overdue loans"
"Which members should I prioritize for collections this week?"
"Create an urgent reminder for Zawadi Njeri's overdue loan"
```

### Forecasting
```
"Forecast loan repayments for next month"
"Predict savings inflows for Q3"
"What's the expected NPL ratio movement?"
```

### Member Analytics
```
"Which members are at risk of churning?"
"Show me retention strategies for inactive members"
"Analyze deposit patterns for high-value members"
```

## 📊 AI Features by Module

| Module | Feature | What to Ask |
|--------|---------|-------------|
| **AI Assistant** | Chat | Any natural language question |
| **Loan Scoring** | Credit analysis | Automatic (view detailed scores) |
| **Fraud Detection** | Anomaly alerts | "Explain flagged transactions" |
| **Collections** | Smart reminders | "Generate collection messages" |
| **Dashboard** | Insights | "Summarize portfolio health" |

## 🎯 Best Practices

### ✅ DO
- Be specific in your queries
- Ask follow-up questions for details
- Reference member names or loan IDs
- Request actionable recommendations

### ❌ DON'T
- Ask vague questions ("Tell me about loans")
- Expect real-time data updates
- Share API keys with others
- Use in untrusted environments (production without backend)

## 💰 Cost Control

### Monitor Usage
Visit: [console.anthropic.com/usage](https://console.anthropic.com/usage)

### Estimate Costs
- Each query: ~1,500-4,000 tokens (~$0.05-0.15)
- 100 queries: ~$5-15
- 1,000 queries: ~$50-150

### Reduce Costs
1. Ask focused questions (not "tell me everything")
2. Use mock mode for testing (disconnect Claude)
3. Set budget alerts in Anthropic console
4. Batch related questions together

## 🔧 Troubleshooting

### Error: "Invalid API key"
```javascript
// Clear old key and set new one
localStorage.removeItem('ANTHROPIC_API_KEY');
localStorage.setItem('ANTHROPIC_API_KEY', 'sk-ant-api03-NEW-KEY');
```
Refresh page.

### Error: "Rate limit exceeded"
Wait 60 seconds, then retry. Or upgrade your Anthropic plan.

### Slow Responses
Normal for complex queries (5-10 seconds). Claude is thinking!

### No Response
1. Check internet connection
2. Verify API key is valid
3. Check browser console for errors
4. Try a simpler question first

## 🎨 Customization

### Change Response Length
Edit `/src/services/claude.ts`:
```typescript
max_tokens: 4096  // Longer (default: 2048)
```

### Use Cheaper Model
Edit `/src/services/claude.ts`:
```typescript
model: "claude-3-haiku-20240307"  // Faster, cheaper
```

### Adjust System Prompt
Edit `buildSaccoContext()` in `/src/services/claude.ts` to customize AI behavior.

## 📱 Mobile/Browser Compatibility

### ✅ Works On
- Chrome, Edge, Safari, Firefox (latest)
- Desktop and mobile browsers
- Any device with localStorage support

### ⚠️ Requires
- Internet connection (API calls to Anthropic)
- localStorage enabled (for API key storage)
- Modern browser (ES6+ support)

## 🔐 Security Reminders

### Development/Internal Use
✅ Current setup is fine for:
- Testing and development
- Internal admin tools
- Trusted users only

### Production/Public Use
⚠️ Must implement:
- Backend proxy for API calls
- Server-side API key storage
- Authentication/authorization
- Rate limiting
- Audit logging

## 📞 Get Help

### Quick Links
- **Setup Guide:** `/GETTING_STARTED_CLAUDE.md`
- **Full Docs:** `/CLAUDE_API_SETUP.md`
- **API Reference:** `/src/services/README.md`
- **Main README:** `/README.md`

### Anthropic Support
- **Docs:** https://docs.anthropic.com
- **Console:** https://console.anthropic.com
- **Status:** https://status.anthropic.com

## 🚀 Pro Tips

1. **Save common queries** - Copy responses you reuse often
2. **Export chat history** - Save important AI insights
3. **Combine questions** - "Show NPL ratio AND overdue loans"
4. **Ask for formats** - "Summarize in bullet points"
5. **Request explanations** - "Why did you recommend X?"
6. **Use context** - "Based on that, what about Y?"

---

**Print this card and keep it handy!** 📋

Need more details? See the full guides in the project root directory.
