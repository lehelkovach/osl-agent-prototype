# Quick Setup: Add Your API Keys

## Your Current Setup

You already have `.env.local` with your OpenAI key. Now add your Claude and Gemini keys!

## Step 1: Get Your API Keys

### Claude (Anthropic)
1. Go to: https://console.anthropic.com/
2. Sign in
3. Go to "API Keys"
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)

### Gemini (Google)
1. Go to: https://makersuite.google.com/app/apikey
2. Sign in with Google
3. Click "Create API Key"
4. Copy the key

## Step 2: Add to `.env.local`

Open your `.env.local` file and add these lines:

```bash
# Add these lines to your existing .env.local file:

# Anthropic Claude (Max subscription)
ANTHROPIC_API_KEY=sk-ant-your-actual-claude-key-here

# Google Gemini (Ultra subscription)
GOOGLE_API_KEY=your-actual-gemini-key-here

# Choose which provider to use (optional)
LLM_PROVIDER=openai  # Change to "claude" or "gemini" to switch
```

## Step 3: Install Packages

```bash
cd /home/johncofax/Dev/git-source/osl-agent-prototype
poetry add anthropic google-generativeai
```

## Step 4: Restart Service

```bash
poetry run agent-service
```

## Done! 

Your agent can now use all three providers. Switch between them by changing `LLM_PROVIDER` in `.env.local`.

