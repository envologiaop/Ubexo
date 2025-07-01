# Envo Telegram Userbot - Render Deployment Guide

## 📦 What You Need

1. The deployment zip file (created below)
2. Render.com account (free)
3. Your API keys:
   - `GEMINI_API_KEY` - From Google AI Studio
   - `TELEGRAM_SESSION_STRING` - Already configured

## 🚀 Step-by-Step Deployment

### Step 1: Download Your Project
Download the `envo-telegram-userbot.zip` file that will be created.

### Step 2: Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up for a free account
3. Verify your email

### Step 3: Deploy Web Service
1. **Click "New +"** in Render dashboard
2. **Select "Web Service"**
3. **Choose "Deploy from Git repository"**
4. **Connect your GitHub** (you'll need to upload the zip to GitHub first)

**OR use direct upload:**
1. **Click "New +"** 
2. **Select "Web Service"**
3. **Choose "Deploy from source code"**
4. **Upload your zip file**

### Step 4: Configure the Service
```
Name: envo-telegram-userbot
Runtime: Python 3
Build Command: pip install -r render_requirements.txt
Start Command: gunicorn --bind 0.0.0.0:$PORT main:app
```

### Step 5: Set Environment Variables
In Render dashboard, add these environment variables:

**Required:**
- `GEMINI_API_KEY` = your_gemini_api_key_here
- `TELEGRAM_SESSION_STRING` = your_session_string_here

**Optional:**
- `SESSION_SECRET` = any_random_string_for_security

### Step 6: Add PostgreSQL Database
1. In Render dashboard, click **"New +"**
2. Select **"PostgreSQL"**
3. Choose **Free plan**
4. Name it: `envo-database`
5. **Copy the Database URL** when created
6. **Add it as environment variable:**
   - `DATABASE_URL` = the_postgresql_url_from_render

### Step 7: Deploy!
1. Click **"Create Web Service"**
2. Wait for deployment (5-10 minutes)
3. Your userbot will be live at: `https://your-app-name.onrender.com`

## 🧪 Testing Your Deployment

1. **Visit your web URL** - you should see the Envo dashboard
2. **Check status** - should show "Ready for Deployment"
3. **Click "Start Bot"** - starts the Telegram userbot
4. **Test in Telegram:**
   - Open any chat
   - Type `.ask hello` or `.help`
   - Your bot should respond naturally!

## 🔧 Troubleshooting

**If bot doesn't respond:**
- Check Render logs for errors
- Verify all environment variables are set
- Click "Start Bot" on the dashboard
- Check your Telegram session is still valid

**If web service crashes:**
- Check the build logs in Render
- Verify all dependencies are in requirements file
- Check environment variables are correctly set

**Database issues:**
- Ensure DATABASE_URL is properly set
- Check PostgreSQL service is running
- Verify connection string format

## 📋 File Structure Included

```
envo-telegram-userbot/
├── app.py                 # Main Flask web application
├── main.py               # Entry point for Render
├── userbot.py            # Telegram userbot logic
├── userbot_service.py    # Standalone userbot service
├── gemini_client.py      # AI response handling
├── models.py             # Database models
├── utils.py              # Utility functions
├── render.yaml           # Render configuration
├── render_requirements.txt # Python dependencies
├── templates/
│   └── dashboard.html    # Web dashboard
└── README.md            # Project documentation
```

## 🎯 Next Steps After Deployment

1. **Bookmark your dashboard URL**
2. **Test all userbot commands in Telegram**
3. **Monitor usage in Render dashboard**
4. **Check logs if any issues arise**

Your Envo userbot is now running 24/7 on Render's free tier! 🎉

## 💡 Pro Tips

- Free tier has 750 hours/month (enough for 24/7)
- Service sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- Use the web dashboard to monitor and restart the bot
- Keep your API keys secure and never share them

---

*Need help? Check the logs in Render dashboard or restart the service.*