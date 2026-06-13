# Gemini AI Service

The chatbot uses `src/services/gemini.ts` and reads the API key from browser local storage:

```js
localStorage.setItem("GEMINI_API_KEY", "your-key")
```

The default model is `gemini-2.5-flash`. Override it with `VITE_GEMINI_MODEL` when needed.

For production, proxy Gemini requests through the backend so API keys are not exposed in browser code.
