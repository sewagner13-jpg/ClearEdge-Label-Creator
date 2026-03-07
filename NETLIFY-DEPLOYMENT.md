# 🚀 Netlify + Railway Deployment Guide

Deploy your Label Creator with:
- **Frontend on Netlify** (static HTML/CSS/JS)
- **Backend on Railway** (FastAPI Python)

---

## Part 1: Deploy Backend to Railway (5 minutes)

### Step 1: Create Railway Account
1. Go to https://railway.app
2. Sign up with GitHub
3. Free tier: $5 credit/month (enough for moderate use)

### Step 2: Deploy from GitHub
1. Click "**New Project**"
2. Select "**Deploy from GitHub repo**"
3. Choose your `ClearEdge-Label-Creator` repository
4. Railway will auto-detect Python and deploy!

### Step 3: Set Environment Variables
1. In Railway project, go to "**Variables**"
2. Add these:
   ```
   GEMINI_API_KEY=AIzaSyBs9RRCTZYT99JgLpP3I7raixF3yJJwvO0
   PORT=8000
   ```

### Step 4: Get Your Backend URL
1. Go to "**Settings**" → "**Networking**"
2. Click "**Generate Domain**"
3. You'll get: `https://your-app-name.railway.app`
4. **Copy this URL** - you'll need it for Netlify!

### Step 5: Enable CORS for Netlify
Add this to your `.env` on Railway (or environment variables):
```bash
ALLOWED_ORIGINS=https://your-netlify-site.netlify.app,http://localhost:8000
```

---

## Part 2: Deploy Frontend to Netlify (3 minutes)

### Step 1: Update API URL
1. Open `netlify-frontend/app.js`
2. Replace line 4 with your Railway URL:
   ```javascript
   const API_URL = window.location.hostname === 'localhost'
       ? 'http://localhost:8000'
       : 'https://YOUR-RAILWAY-APP.railway.app';  // ← UPDATE THIS
   ```

### Step 2: Create Netlify Account
1. Go to https://netlify.com
2. Sign up with GitHub
3. 100% free for static sites

### Step 3: Deploy
1. Click "**Add new site**" → "**Import an existing project**"
2. Connect to GitHub
3. Choose your `ClearEdge-Label-Creator` repository
4. Set these build settings:
   ```
   Base directory: netlify-frontend
   Build command: (leave empty)
   Publish directory: .
   ```
5. Click "**Deploy**"

### Step 4: Get Your Site URL
You'll get: `https://your-site-name.netlify.app`

### Step 5: Update CORS on Railway
Go back to Railway and update `ALLOWED_ORIGINS` with your Netlify URL:
```
ALLOWED_ORIGINS=https://your-site-name.netlify.app,http://localhost:8000
```

---

## ✅ You're Live!

Your app is now deployed at:
- **Frontend**: `https://your-site-name.netlify.app`
- **Backend API**: `https://your-app-name.railway.app`

---

## 🔧 Testing Your Deployment

### Test Backend API:
```bash
curl https://your-app-name.railway.app/
```

Should return the FastAPI homepage HTML.

### Test Frontend:
1. Open `https://your-site-name.netlify.app`
2. Upload a test SDS PDF
3. Enter a product name
4. Generate label
5. Download PDF!

---

## 📊 Monitoring & Logs

### Railway:
- View logs in real-time in the Railway dashboard
- Monitor resource usage (RAM, CPU)
- Free tier: 512MB RAM, $5/month credit

### Netlify:
- View build logs
- Monitor bandwidth (100GB/month free)
- Instant deploys on git push

---

## 🔄 Auto-Deploy Setup

### Railway (Backend):
- ✅ Auto-deploys on push to `main` branch
- ✅ No configuration needed

### Netlify (Frontend):
1. Go to "**Site settings**" → "**Build & deploy**"
2. Set:
   ```
   Base directory: netlify-frontend
   Build command: (empty)
   Publish directory: .
   ```
3. ✅ Auto-deploys when `netlify-frontend/` changes

---

## 💰 Cost Breakdown

### Railway (Backend):
- **Free tier**: $5 credit/month
- **Usage**: ~$3-4/month for light use
- **If you exceed**: $0.000231/GB-hour RAM

### Netlify (Frontend):
- **100% FREE** for static sites
- **Bandwidth**: 100GB/month free
- **Build minutes**: 300/month free

**Total cost**: ~$0-5/month depending on usage

---

## 🚀 Quick Deploy Commands

### One-Time Setup:
```bash
# 1. Commit frontend files
git add netlify-frontend/ railway.json
git commit -m "feat: add Netlify + Railway deployment config"
git push

# 2. Deploy backend to Railway (via web UI)
# 3. Deploy frontend to Netlify (via web UI)
```

### Future Updates:
```bash
# Just push to git - auto-deploys!
git add .
git commit -m "update: improve label template"
git push
```

---

## 🔐 Security Checklist

- ✅ HTTPS enabled (automatic on both platforms)
- ✅ CORS configured
- ✅ API key in environment variables (not in code)
- ✅ Path traversal protection enabled
- ✅ Input validation on all endpoints
- ✅ File upload size limits

---

## 🐛 Troubleshooting

### Backend returns 500 error:
1. Check Railway logs: `Project` → `Deployments` → `View Logs`
2. Common issues:
   - Missing environment variables
   - Dependency installation failed
   - Port configuration

### Frontend can't connect to backend:
1. Check API_URL in `app.js` is correct
2. Check CORS is configured on Railway
3. Test backend directly: `curl https://your-railway-app.railway.app/`

### Label generation fails:
1. Check Gemini API key is valid
2. Check Railway logs for errors
3. Test with smaller PDF first

---

## 📝 Environment Variables Reference

### Railway (Backend):
```bash
GEMINI_API_KEY=your_key_here
PORT=8000
ALLOWED_ORIGINS=https://your-netlify-site.netlify.app,http://localhost:8000
LOG_LEVEL=INFO
```

### Netlify (Frontend):
None needed - static site!

---

## 🎉 Next Steps

1. **Custom Domain**:
   - Netlify: Add custom domain in "**Domain settings**"
   - Railway: Add custom domain in "**Settings**" → "**Networking**"

2. **Analytics**:
   - Netlify has built-in analytics
   - Railway shows deployment metrics

3. **Backups**:
   - All code in GitHub (auto-backup)
   - Railway has automatic daily backups

4. **Scaling**:
   - Railway: Increase resources in settings
   - Netlify: Scales automatically (serverless)

---

## 📧 Support

- Railway: https://railway.app/help
- Netlify: https://docs.netlify.com
- Issues: GitHub repo issues

---

**Deployment complete!** Your professional label creator is now live on the web! 🎊
