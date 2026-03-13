# 🥗 FoodResQ

> Making surplus food discoverable in real time.
> Connects bakeries and cafes with excess food to nearby users before it gets thrown away.

---

## Project structure

```
foodresq/
├── app.py              # Streamlit UI (3 tabs: Search, Add Listing, Impact)
├── elastic.py          # All Elasticsearch logic (search, index, metrics, seed)
├── requirements.txt
├── .env.example        # Copy to .env and fill in your credentials
├── .gitignore
├── foodresq.service    # systemd unit for EC2 auto-start
└── README.md
```

---

## Part 1 – Connect to Elastic Cloud

### Step 1 – Create a deployment

1. Go to https://cloud.elastic.co and sign in (free trial available).
2. Click **Create deployment** → choose **AWS** as provider → pick region `ap-southeast-1` (Singapore).
3. Click **Create deployment** and wait ~3 minutes.
4. **Save the `elastic` password** shown at the end — you only see it once.

### Step 2 – Get your endpoint URL

1. In the Elastic Cloud console, click your deployment.
2. Under **Elasticsearch**, copy the **Endpoint** URL. It looks like:
   ```
   https://abc123.es.ap-southeast-1.aws.elastic.cloud:443
   ```

### Step 3 – Create an API key (recommended over password)

1. Open **Kibana** (click the Kibana link in your deployment).
2. Go to **Stack Management → API Keys → Create API key**.
3. Give it a name (e.g. `foodresq-key`), no expiry for hackathon use.
4. Copy the **Base64** value shown.

### Step 4 – Set your .env

```bash
cp .env.example .env
```

Edit `.env`:

```env
ES_URL=https://abc123.es.ap-southeast-1.aws.elastic.cloud:443
ES_API_KEY=your_base64_key_here
```

---

## Part 2 – Run locally

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Open http://localhost:8501 in your browser.

On first launch, 15 sample Singapore food listings are seeded automatically.

---

## Part 3 – Deploy on AWS EC2

### Step 1 – Launch an EC2 instance

1. Go to **AWS Console → EC2 → Launch Instance**.
2. Choose:
   - **AMI**: Ubuntu Server 22.04 LTS (free tier eligible)
   - **Instance type**: `t2.micro` (free tier) or `t3.small` for better performance
   - **Key pair**: Create a new key pair, download the `.pem` file
3. Under **Network settings**, click **Edit** and add an inbound rule:
   - **Type**: Custom TCP
   - **Port**: `8501`
   - **Source**: `0.0.0.0/0` (or restrict to your IP for security)
4. Click **Launch instance**.

### Step 2 – Connect to your instance

```bash
# Fix key permissions
chmod 400 your-key.pem

# SSH in (replace with your EC2 public IP/DNS)
ssh -i your-key.pem ubuntu@YOUR-EC2-PUBLIC-IP
```

### Step 3 – Install dependencies on EC2

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3-pip python3-venv -y

# Verify
python3 --version
```

### Step 4 – Upload your app

**Option A – SCP (simple, from your local machine):**
```bash
# From your local machine, in the foodresq/ directory:
scp -i your-key.pem -r . ubuntu@YOUR-EC2-PUBLIC-IP:/home/ubuntu/foodresq
```

**Option B – Git (if you push to GitHub):**
```bash
# On the EC2 instance:
git clone https://github.com/YOUR-USERNAME/foodresq.git
cd foodresq
```

### Step 5 – Configure the environment

```bash
cd /home/ubuntu/foodresq

# Create your .env with real credentials
cp .env.example .env
nano .env
# Paste your ES_URL and ES_API_KEY, then Ctrl+X → Y → Enter to save
```

### Step 6 – Install Python packages

```bash
cd /home/ubuntu/foodresq
pip3 install -r requirements.txt
```

### Step 7 – Test it runs

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Open your browser at: `http://YOUR-EC2-PUBLIC-IP:8501`

Press `Ctrl+C` to stop once confirmed working.

### Step 8 – Run as a background service (auto-restart)

```bash
# Copy the systemd service file
sudo cp foodresq.service /etc/systemd/system/foodresq.service

# Reload systemd, enable and start
sudo systemctl daemon-reload
sudo systemctl enable foodresq
sudo systemctl start foodresq

# Check status
sudo systemctl status foodresq

# View live logs
sudo journalctl -u foodresq -f
```

The app will now start automatically on reboot.

---

## Useful commands

| Task | Command |
|------|---------|
| Restart app | `sudo systemctl restart foodresq` |
| Stop app | `sudo systemctl stop foodresq` |
| View logs | `sudo journalctl -u foodresq -f` |
| Check app is live | `curl http://localhost:8501` |
| Re-upload files | `scp -i key.pem -r . ubuntu@IP:/home/ubuntu/foodresq` |

---

## Demo flow (pitch)

1. Open the **Search** tab → search `croissant` → set radius to 5 km → hit Search
2. Show ranked results with distance, saving amount, and pickup time
3. Switch to **Add Listing** tab → add a new item as a merchant → click Publish
4. Switch back to **Search** → search again → new item appears instantly
5. Open **Impact** tab → show total listings, meals rescued, and savings

---

## Architecture

```
User / Merchant browser
        │
        ▼
  Streamlit app (EC2 :8501)
        │
        ▼
  elastic.py
        │  HTTPS / API key
        ▼
  Elastic Cloud (AWS-hosted)
  └── food_items index
       ├── geo_point location field
       ├── pickup_end date filter
       └── full-text title + description
```
