# 🚀 AWS EC2 Deployment Guide for E2M RAG Backend

This guide covers everything you need to deploy your FastAPI backend to a raw AWS EC2 instance. This will give you 24/7 uptime (no sleeping like Render) and faster CPU performance for embeddings.

---

## Step 1: Launch an EC2 Instance

1. Log in to the [AWS Management Console](https://console.aws.amazon.com/).
2. Search for **EC2** and click **Launch Instance**.
3. **Name**: `E2M-Backend`
4. **OS Images (AMI)**: Select **Ubuntu** (Ubuntu Server 24.04 LTS or 22.04 LTS).
5. **Instance Type**: Select **t3.micro** or **t2.micro** *(These are Free Tier eligible)*.
6. **Key Pair**: 
   - Click **Create new key pair**.
   - Name it `e2m-key`.
   - Download the `.pem` file and keep it safe on your computer.
7. **Network Settings**:
   - Check **Allow SSH traffic from Anywhere**.
   - Check **Allow HTTP traffic from the internet**.
   - Check **Allow HTTPS traffic from the internet**.
8. Click **Launch Instance**.

---

## Step 2: Open Port 8000 (Important!)
By default, AWS blocks all ports except SSH (22) and HTTP (80). Since our backend runs on port 8000, we must open it.

1. Go to your **EC2 Dashboard**, click on your new `E2M-Backend` instance.
2. At the bottom, click the **Security** tab, then click the **Security Group** link (e.g., `sg-0abcd1234`).
3. Click **Edit inbound rules** -> **Add rule**.
4. Set **Type** to `Custom TCP`, **Port range** to `8000`, and **Source** to `Anywhere-IPv4` (`0.0.0.0/0`).
5. Click **Save rules**.

---

## Step 3: Connect to your EC2 Server

Open a terminal on your computer. Navigate to the folder where you downloaded `e2m-key.pem` and run these commands (replace `<EC2_PUBLIC_IP>` with your instance's Public IPv4 address found in the AWS console):

**Mac/Linux:**
```bash
chmod 400 e2m-key.pem
ssh -i "e2m-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

**Windows (PowerShell):**
```powershell
ssh -i .\e2m-key.pem ubuntu@<EC2_PUBLIC_IP>
```
*(Type `yes` if it asks about fingerprinting).*

---

## Step 4: Clone and Install Your App

Once you are logged into the Ubuntu terminal on AWS, run the following commands one by one to install Python, Git, and your app:

```bash
# 1. Update the server packages
sudo apt update && sudo apt upgrade -y

# 2. Install Python, pip, and virtualenv
sudo apt install python3-pip python3-venv git -y

# 3. Clone your repository (Replace with your actual GitHub URL)
git clone https://github.com/Ansh-DSML/E2M-RAG-Assistant.git
cd E2M-RAG-Assistant

# 4. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt
```

---

## Step 5: Configure your Environment Variables

You need to create your `.env` file on the server since it wasn't pushed to GitHub.

```bash
nano .env
```
Paste your entire `.env` configuration into the file. It should look like this:

```env
GROQ_API_KEY=your_key
COHERE_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
QDRANT_URL=your_url
QDRANT_API_KEY=your_key

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT="E2M-RAG-Assistant"
GROQ_API_KEY_JUDGE=your_judge_key

# Make sure your Vercel frontend URL is here!
CORS_ORIGINS=http://localhost:3000,https://e2-m-rag-assistant-weld.vercel.app
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,docx
```
Press `CTRL+O`, then `Enter` to save. Press `CTRL+X` to exit.

---

## Step 6: Run the Server 24/7 (Using `tmux`)

If you just run `uvicorn`, it will die as soon as you close your terminal. To keep it running forever in the background, we use a tool called `tmux`.

```bash
# 1. Start a new background session
tmux new -s backend

# 2. Make sure you are in the folder and venv is active
cd ~/E2M-RAG-Assistant
source .venv/bin/activate

# 3. Start the server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> **To safely detach (leave it running in the background):**
> Press `Ctrl+B`, release both keys, then press `D`.

*(If you ever need to see the logs again, log into the server and type `tmux attach -t backend`).*

---

## Step 7: Connect Vercel to AWS!

Your backend is now live at: `http://<EC2_PUBLIC_IP>:8000`

Go to your **Vercel Dashboard** -> **Settings** -> **Environment Variables**.
1. Update `NEXT_PUBLIC_API_URL` to: `http://<EC2_PUBLIC_IP>:8000`
2. **Redeploy your Vercel frontend** so it picks up the new IP address.

You are done! Your frontend is now cleanly separated on Vercel, talking to a dedicated, high-performance AWS EC2 server running 24/7.
