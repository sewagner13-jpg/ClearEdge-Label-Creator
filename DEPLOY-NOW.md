# 🚀 Deploy Your Label Creator (Netlify + Railway)

**Total time: 10 minutes**

---

## Part 1: Deploy Backend to Railway (5 min)

### 1. Create Railway Account
- Go to https://railway.app
- Click "Login with GitHub"
- **Free**: $5 credit/month (covers ~1000 labels)

### 2. Deploy Backend
1. Click "**New Project**"
2. Select "**Deploy from GitHub repo**"
3. Choose `ClearEdge-Label-Creator`
4. Railway auto-detects Python ✅
5. Wait 2-3 minutes for deployment

### 3. Add Environment Variable
1. Go to "**Variables**" tab
2. Click "**+ New Variable**"
3. Add:
   ```
   GEMINI_API_KEY
   AIzaSyBs9RRCTZYT99JgLpP3I7raixF3yJJwvO0
   ```
4. Click "**Add**"

### 4. Get Your API URL
1. Go to "**Settings**" tab
2. Scroll to "**Networking**"
3. Click "**Generate Domain**"
4. Copy the URL (looks like: `https://clearedge-label-creator-production.up.railway.app`)

**✅ Backend is live!**

---

## Part 2: Update Frontend Code (2 min)

### 1. Update API URL
Open `netlify-frontend/app.js` and change line 4:

**Replace:**
```javascript
: 'https://YOUR-RAILWAY-APP.railway.app';
```

**With your Railway URL:**
```javascript
: 'https://clearedge-label-creator-production.up.railway.app';
```

### 2. Commit the Change
```bash
git add netlify-frontend/app.js
git commit -m "config: set Railway API URL"
git push
```

---

## Part 3: Deploy Frontend to Netlify (3 min)

### 1. Go to Netlify Dashboard
- Login to https://app.netlify.com

### 2. Deploy Site
1. Click "**Add new site**" → "**Import an existing project**"
2. Choose "**Deploy with GitHub**"
3. Select your `ClearEdge-Label-Creator` repo
4. Configure build settings:
   ```
   Base directory: netlify-frontend
   Build command: (leave empty)
   Publish directory: .
   ```
5. Click "**Deploy site**"

### 3. Wait 1 minute
Netlify will deploy your site!

### 4. Get Your URL
Copy your site URL (looks like: `https://clearedge-label-creator.netlify.app`)

**✅ Frontend is live!**

---

## Part 4: Enable CORS (1 min)

### Update Backend CORS
1. Go back to Railway
2. Click "**Variables**"
3. Add new variable:
   ```
   ALLOWED_ORIGINS
   https://clearedge-label-creator.netlify.app
   ```
   (Use YOUR Netlify URL)
4. Backend will auto-redeploy (30 seconds)

**✅ CORS enabled!**

---

## 🎉 YOU'RE LIVE!

Test your app:
1. Go to your Netlify URL
2. Upload a test SDS PDF
3. Enter product name
4. Generate label
5. Download PDF!

---

## 📊 Your Deployment

| Component | Platform | URL | Cost |
|-----------|----------|-----|------|
| Frontend | Netlify | `your-site.netlify.app` | Included in your plan |
| Backend API | Railway | `your-app.railway.app` | ~$3/month (free $5 credit) |

**Total cost: Effectively $0** (covered by Railway's free credit)

---

## 🔄 Future Updates

**To update your app:**
```bash
# Make changes to code
git add .
git commit -m "update: improve labels"
git push
```

- ✅ Railway auto-deploys backend
- ✅ Netlify auto-deploys frontend
- ✅ No manual steps needed!

---

## 🔐 Custom Domain (Optional)

### On Netlify:
1. Go to "**Domain settings**"
2. Click "**Add custom domain**"
3. Enter: `labels.clear-edge.net`
4. Follow DNS setup instructions

### On Railway:
1. Go to "**Settings**" → "**Networking**"
2. Click "**Custom Domain**"
3. Enter: `api.clear-edge.net`
4. Add CNAME record to your DNS

---

## 📈 Monitoring

### Railway Dashboard:
- View real-time logs
- Monitor CPU/RAM usage
- See request metrics

### Netlify Dashboard:
- Build logs
- Bandwidth usage (you have plenty!)
- Form submissions (if you add contact form)

---

## 🐛 Troubleshooting

### "Failed to fetch" error:
1. Check Railway app is running (green status)
2. Verify API URL in `app.js` matches Railway URL
3. Check CORS is configured with your Netlify URL

### Backend crashes:
1. Check Railway logs for errors
2. Verify GEMINI_API_KEY is set
3. Check dependencies installed correctly

### Label generation fails:
1. Test Gemini API key: https://aistudio.google.com
2. Check Railway logs for specific error
3. Try with a smaller PDF first

---

## ✅ Deployment Checklist

- [ ] Railway account created
- [ ] Backend deployed to Railway
- [ ] GEMINI_API_KEY added to Railway
- [ ] Railway domain generated
- [ ] API URL updated in app.js
- [ ] Code committed and pushed
- [ ] Frontend deployed to Netlify
- [ ] ALLOWED_ORIGINS added to Railway
- [ ] Test: Upload PDF and generate label
- [ ] Success: Download PDF label!

---

**Need help?** Check the full guide: `NETLIFY-DEPLOYMENT.md`

**Ready to deploy?** Start with Part 1 above! 🚀
