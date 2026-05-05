# Netlify Deployment

The frontend is a static app in `netlify-frontend/`.

Root `netlify.toml` publishes that directory:

```toml
[build]
  publish = "netlify-frontend"
  command = "echo 'No build needed - static site'"
```

The frontend reads its backend URL from `netlify-frontend/config.js`:

```js
window.CLEAREDGE_API_URL = 'https://clearedgelabelcreator-production.up.railway.app';
```

After deployment, verify:

```bash
curl https://clearedge-label-creator.netlify.app/
curl https://clearedge-label-creator.netlify.app/config.js
```
