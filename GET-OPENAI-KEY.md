# 🔑 Get Your OpenAI API Key (2 minutes)

Your label creator now uses **ChatGPT** (OpenAI) for AI extraction instead of Gemini.

---

## Step 1: Create OpenAI Account

1. Go to https://platform.openai.com
2. Click **"Sign up"** (or Login if you have an account)
3. Use your email or Google/Microsoft account

---

## Step 2: Add Payment Method

**Important:** OpenAI requires a payment method, but usage is very cheap:

1. Go to **Settings** → **Billing**
2. Click **"Add payment method"**
3. Add credit/debit card
4. Set a **spending limit** (recommended: $10/month)

**Cost estimate for labels:**
- ~$0.01 per label (using GPT-4o)
- ~$0.002 per label (using GPT-3.5-turbo)
- **100 labels ≈ $1** with GPT-4o

---

## Step 3: Get Your API Key

1. Click your profile (top right)
2. Go to **"API keys"**
3. Click **"Create new secret key"**
4. Name it: `Label Creator`
5. Click **"Create secret key"**
6. **COPY the key immediately** (starts with `sk-proj-...`)

⚠️ **SAVE IT NOW** - You can't see it again!

---

## Step 4: Use Your API Key

**For Railway deployment:**
```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
```

**For local testing:**
Create `.env` file:
```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
```

---

## 🎯 Which Model to Use?

**Recommended: GPT-4o** (default)
- ✅ Best accuracy for SDS extraction
- ✅ Handles complex documents
- 💰 ~$0.01 per label

**Budget option: GPT-4o-mini**
- ✅ 10x cheaper (~$0.001 per label)
- ⚠️ Slightly less accurate
- ✅ Good for simple SDSs

**To change model:**
In Railway, add environment variable:
```
OPENAI_MODEL=gpt-4o-mini
```

---

## 💳 Billing & Limits

**Free tier:** $5 credit (expires after 3 months for new accounts)

**Pay-as-you-go pricing:**
- GPT-4o: $0.005 per 1K input tokens (~$0.01 per label)
- GPT-4o-mini: $0.00015 per 1K input tokens (~$0.001 per label)

**Set spending limits:**
1. Settings → Billing → Usage limits
2. Set **Hard limit**: $10/month
3. Set **Email alert**: $5

---

## 🔐 Security Best Practices

✅ **DO:**
- Store key in Railway environment variables
- Set spending limits
- Rotate key every 90 days
- Use separate keys for dev/prod

❌ **DON'T:**
- Commit key to git
- Share key publicly
- Use same key across projects
- Leave unlimited spending

---

## 🧪 Test Your Key

**Before deploying, test locally:**

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE" > .env

# Run app
python -m uvicorn simple_app:app --reload

# Open browser
# http://localhost:8000
```

Upload a test SDS and generate a label!

---

## ✅ Checklist

- [ ] OpenAI account created
- [ ] Payment method added (required)
- [ ] Spending limit set ($10/month)
- [ ] API key generated (sk-proj-...)
- [ ] Key saved securely
- [ ] Key added to Railway (OPENAI_API_KEY)
- [ ] Model selected (gpt-4o or gpt-4o-mini)
- [ ] Test label generated successfully

---

## 🆚 OpenAI vs Gemini

**Why switch to OpenAI?**

| Feature | OpenAI (GPT-4o) | Gemini |
|---------|----------------|--------|
| Accuracy | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Speed | Fast | Fast |
| Cost | ~$0.01/label | Free* |
| Reliability | Very high | High |
| JSON mode | Native | Beta |
| Rate limits | Generous | Generous |

*Gemini free tier has lower limits

**Bottom line:** OpenAI is more reliable for production use!

---

## 🐛 Troubleshooting

### "Invalid API key" error
- Check key starts with `sk-proj-` (new format) or `sk-` (old format)
- Verify no extra spaces when copying
- Try regenerating the key

### "Insufficient quota" error
- Add payment method to account
- Check billing dashboard for issues
- Verify spending limit not reached

### "Rate limit exceeded"
- Wait 1 minute and retry
- Upgrade to paid tier for higher limits
- Use GPT-4o-mini for lower rate limits

### "Model not found"
- Check model name: `gpt-4o` (not `gpt-4-o`)
- Try: `gpt-4-turbo` or `gpt-3.5-turbo`

---

**Ready?** Get your key and continue with deployment! 🚀

**Next step:** Open `DEPLOY-NOW.md` and follow Part 1
