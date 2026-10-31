# Deployment Guide: LinkedIn Post Generator on AWS EC2

This guide takes the project from your Windows machine to a public website on a single AWS EC2
instance. Each section builds on the previous one, so follow them in order the first time.

For running the project locally, see [user_manual.md](user_manual.md).

---

## Contents

0. [Overview](#0-overview)
1. [Before you start](#1-before-you-start)
2. [Launch the EC2 instance](#2-launch-the-ec2-instance)
3. [Connect over SSH](#3-connect-over-ssh)
4. [Prepare the server](#4-prepare-the-server)
5. [Install and connect Ollama](#5-install-and-connect-ollama)
6. [Get the code onto the server](#6-get-the-code-onto-the-server)
7. [Set up the backend as a service](#7-set-up-the-backend-as-a-service)
8. [Build and publish the frontend](#8-build-and-publish-the-frontend)
9. [Configure nginx](#9-configure-nginx)
10. [Verify the deployment](#10-verify-the-deployment)
11. [Add a domain and HTTPS](#11-add-a-domain-and-https)
12. [Deploy updates](#12-deploy-updates)
13. [Operate the server](#13-operate-the-server)
14. [Security checklist](#14-security-checklist)
15. [Troubleshooting](#15-troubleshooting)
16. [Costs and cleanup](#16-costs-and-cleanup)
17. [Alternatives](#17-alternatives)

---

## 0. Overview

### What you will end up with

```
                 Internet
                    │
        ┌───────────▼────────────┐   Security group: 80/443 open to everyone,
        │       EC2 instance     │                   22 open to your IP only
        │                        │
        │   nginx  :80 / :443    │
        │    ├── /        ──────►│  static React build  (/var/www/linkedin-post-generator)
        │    └── /api/*   ──────►│  uvicorn + FastAPI   (127.0.0.1:8000, systemd service)
        │                        │        │
        │                        │        ▼
        │                        │  Ollama              (127.0.0.1:11434, systemd service)
        └────────────────────────┘        │
                                          ▼  cloud model (gpt-oss:20b-cloud)
                                     ollama.com
```

### Why this design

| Decision | Reason |
|----------|--------|
| **nginx in front of everything** | Serves the React files efficiently, forwards `/api` to FastAPI, adds HTTPS, rate limiting and timeouts. |
| **Frontend and API on the same address** | The browser only ever talks to nginx, so you don't need CORS settings or `VITE_API_BASE_URL`. |
| **FastAPI and Ollama bound to `127.0.0.1`** | Only nginx can reach them. Neither has any login of its own, so they must never be public. |
| **systemd services** | Ollama and the backend start on boot and restart automatically if they crash. |
| **Ollama cloud model** | `gpt-oss:20b-cloud` runs on ollama.com, so the server only proxies requests. No GPU and very little RAM are needed. |

### Values you will need

Keep these at hand; the guide refers to them by these placeholder names:

| Placeholder | Example | Where it comes from |
|-------------|---------|---------------------|
| `<KEY_FILE>` | `C:\Users\chaks\.ssh\linkedin-key.pem` | Key pair you download in section 2 |
| `<SERVER_IP>` | `3.110.25.40` | Elastic IP from section 2.6 |
| `<YOUR_DOMAIN>` | `posts.example.com` | Optional, section 11 |

---

## 1. Before you start

### 1.1 Checklist

- [ ] An AWS account with billing set up
- [ ] An ollama.com account (needed for the cloud model)
- [ ] The project working locally (see `user_manual.md`)
- [ ] All code committed and pushed to GitHub (section 1.2)
- [ ] Optional: a domain name, if you want HTTPS (section 11)

### 1.2 Push your code to GitHub

The server gets the code with `git clone`, so everything must be on GitHub first.
From the project root on Windows:

```powershell
git add .gitignore README.md requirement.txt user_manual.md deployment_guide.md backend frontend
git status
```

Check the `git status` output before committing. It must **not** list `.env`, `node_modules`,
`.venv` or `__pycache__`; the `.gitignore` files exclude them. Then:

```powershell
git commit -m "Add FastAPI backend, React frontend and documentation"
git push origin main
```

> `.env` is deliberately not pushed. You create a separate one on the server in section 6.3.

---

## 2. Launch the EC2 instance

In the AWS Console, pick a **region** close to you or your users (top-right corner), open
**EC2 → Instances → Launch instances** and fill in the form as follows.

### 2.1 Name and image (AMI)

- **Name:** `linkedin-post-generator`
- **AMI:** **Ubuntu Server 24.04 LTS**, 64-bit (x86)

This guide's commands assume Ubuntu 24.04. It includes Python 3.12, which this project runs on.

### 2.2 Instance type

| Type | vCPU | RAM | Verdict |
|------|------|-----|---------|
| t3.micro | 2 | 1 GiB | Works only with a swap file (section 4.3), or if you build the frontend on your PC (section 17) |
| **t3.small** | 2 | 2 GiB | **Recommended minimum** |
| t3.medium | 2 | 4 GiB | Comfortable headroom |

These sizes work because the cloud model runs on ollama.com. If you later switch to a model that
runs *on the server* (a non-`-cloud` model), you need far more RAM, and realistically a GPU
instance.

### 2.3 Key pair

Click **Create new key pair**:

- **Name:** `linkedin-key`
- **Type:** ED25519 (or RSA)
- **Format:** `.pem`

The file downloads once. Move it somewhere safe, such as `C:\Users\<you>\.ssh\`. Without it you
cannot log in to the server.

### 2.4 Network settings (security group)

Click **Edit** and create a security group with exactly these inbound rules:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | **My IP** | Your admin access only |
| HTTP | 80 | Anywhere (0.0.0.0/0 and ::/0) | The website |
| HTTPS | 443 | Anywhere (0.0.0.0/0 and ::/0) | The website over HTTPS |

> **Do not** open port 8000 (FastAPI) or 11434 (Ollama). nginx reaches both internally.
> Ollama in particular has no authentication, so an open 11434 lets anyone use your ollama.com account.

### 2.5 Storage

- **20 GiB gp3** is plenty (the OS, Ollama, Node, Python packages and the build).

Click **Launch instance**.

### 2.6 Give the server a fixed IP (Elastic IP)

A normal public IP changes every time the instance stops and starts. To keep it fixed:

1. **EC2 → Network & Security → Elastic IPs → Allocate Elastic IP address → Allocate**
2. Select the new IP → **Actions → Associate Elastic IP address**
3. Choose your `linkedin-post-generator` instance → **Associate**

This address is your `<SERVER_IP>` from now on.

---

## 3. Connect over SSH

From PowerShell on Windows.

### 3.1 Restrict the key file's permissions (once)

Windows OpenSSH refuses keys that other users could read
(error: `UNPROTECTED PRIVATE KEY FILE`). Lock the file down to your user:

```powershell
icacls "<KEY_FILE>" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### 3.2 Connect

```powershell
ssh -i "<KEY_FILE>" ubuntu@<SERVER_IP>
```

Type `yes` the first time to trust the server. Ubuntu AMIs use the username **`ubuntu`**.

**Every command from here until section 12 runs on the server**, inside this SSH session,
unless it says otherwise.

---

## 4. Prepare the server

### 4.1 Update the system and install packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx git rsync
```

If the upgrade installed a new kernel, reboot and reconnect:

```bash
[ -f /var/run/reboot-required ] && sudo reboot
```

### 4.2 Install Node.js 24

The frontend needs Node.js 22.22 or newer, but Ubuntu's own `nodejs` package is older.
Install it from NodeSource instead. Downloading the script to a file first lets you look at it
before running it:

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x -o nodesource_setup.sh
sudo bash nodesource_setup.sh
sudo apt install -y nodejs
node -v      # should print v24.x
npm -v
```

### 4.3 Add swap (t3.micro, or if `npm run build` gets killed)

The frontend build briefly needs more memory than a 1 GiB instance has. A 2 GiB swap file
prevents out-of-memory crashes:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h      # the Swap row should show 2.0Gi
```

---

## 5. Install and connect Ollama

### 5.1 Install

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The installer creates an `ollama` system user and an `ollama` systemd service that starts on boot.
A warning that no GPU was found is expected and harmless for cloud models.

Check it is running:

```bash
systemctl status ollama --no-pager
```

### 5.2 Sign in to ollama.com

Cloud models need the server linked to your Ollama account:

```bash
ollama signin
```

The server has no browser, so this **prints a URL**. Open that URL on your own computer, sign in
to ollama.com and approve the connection. The command on the server then finishes by itself.

### 5.3 Pull and test the model

```bash
ollama pull gpt-oss:20b-cloud
ollama list                                        # cloud models show "-" as their size
ollama run gpt-oss:20b-cloud "Say hello in five words"
```

If the last command prints a short reply, Ollama is ready.

> Ollama listens only on `127.0.0.1:11434` by default. Never set `OLLAMA_HOST=0.0.0.0` on this
> server and never open port 11434 in the security group.

---

## 6. Get the code onto the server

### 6.1 Clone the repository

```bash
cd ~
git clone https://github.com/ChakshuGrover225/LinkedIn_Content_generation.git
cd LinkedIn_Content_generation
ls      # backend  frontend  requirement.txt  user_manual.md  ...
```

The project now lives in `/home/ubuntu/LinkedIn_Content_generation`. The rest of the guide uses
that path.

### 6.2 If the repository is private

GitHub does not accept your account password for `git clone`. Either:

- create a **fine-grained personal access token** on GitHub with read-only access to this
  repository's *Contents*, and paste it when `git clone` asks for a password, or
- create an SSH key on the server with `ssh-keygen -t ed25519` (press Enter at every prompt), add
  the contents of `~/.ssh/id_ed25519.pub` as a read-only **deploy key** in the repository's
  *Settings → Deploy keys*, and clone with
  `git clone git@github.com:ChakshuGrover225/LinkedIn_Content_generation.git`.

### 6.3 Create the server's `.env` (optional)

All settings have working defaults for this setup, so `.env` is optional. Create one only to change
them:

```bash
nano ~/LinkedIn_Content_generation/.env
```

```ini
LLM_MODEL=gpt-oss:20b-cloud
LLM_BASE_URL=http://localhost:11434
```

Save with **Ctrl+O, Enter**, exit with **Ctrl+X**, then make it readable only by you:

```bash
chmod 600 ~/LinkedIn_Content_generation/.env
```

`CORS_ORIGINS` is not needed: nginx serves the frontend and the API from the same address.

---

## 7. Set up the backend as a service

### 7.1 Create the Python environment

```bash
cd ~/LinkedIn_Content_generation
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirement.txt
```

### 7.2 Smoke test

Run the whole writer → critic → reviser chain once from the terminal:

```bash
.venv/bin/python backend/orchestrator.py
```

After 15 to 60 seconds it should print a LinkedIn post. If it does, the code, the Python packages
and Ollama all work together. If it fails, fix that first (section 15); nothing later can work
without it.

### 7.3 Create the systemd service

This makes the backend start on boot and restart if it crashes:

```bash
sudo tee /etc/systemd/system/linkedin-backend.service > /dev/null <<'EOF'
[Unit]
Description=LinkedIn Post Generator API (FastAPI + uvicorn)
After=network.target ollama.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/LinkedIn_Content_generation/backend
ExecStart=/home/ubuntu/LinkedIn_Content_generation/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

What the important lines do:

| Line | Why |
|------|-----|
| `WorkingDirectory=.../backend` | uvicorn must start inside `backend/` to find the `app` and `logic` packages. |
| `--host 127.0.0.1` | Only reachable from the server itself, which means only via nginx. |
| `--workers 2` | One process per vCPU. Each process already handles several requests at once, so two is plenty. |
| No `--reload` | Auto-reload is a development feature. In production you restart deliberately. |
| `Restart=on-failure` | systemd brings the API back if it crashes. |

### 7.4 Start it

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now linkedin-backend
systemctl status linkedin-backend --no-pager      # should say "active (running)"
curl -s http://127.0.0.1:8000/api/health          # {"status":"ok"}
```

---

## 8. Build and publish the frontend

### 8.1 Build

```bash
cd ~/LinkedIn_Content_generation/frontend
npm ci
npm run build
```

`npm ci` installs the exact versions recorded in `package-lock.json`. The build writes static files
to `frontend/dist/`.

Leave `VITE_API_BASE_URL` unset. The frontend then calls `/api/...` on the same address it was
loaded from, which is nginx.

### 8.2 Publish to the web root

```bash
sudo mkdir -p /var/www/linkedin-post-generator
sudo rsync -a --delete dist/ /var/www/linkedin-post-generator/
ls /var/www/linkedin-post-generator      # index.html  assets
```

**Why copy instead of pointing nginx at `frontend/dist`?** On Ubuntu 24.04, home directories are
private (permissions `750`). nginx runs as the `www-data` user and cannot read anything inside
`/home/ubuntu`, which would give you 403 or 404 errors. `--delete` removes old build files that a
new build no longer uses.

---

## 9. Configure nginx

### 9.1 Create the site configuration

```bash
sudo tee /etc/nginx/sites-available/linkedin-post-generator > /dev/null <<'EOF'
# Each generation costs three LLM calls: allow 5 per minute per visitor (plus a burst of 3).
limit_req_zone $binary_remote_addr zone=generate:10m rate=5r/m;

server {
    listen 80;
    listen [::]:80;
    server_name _;

    root /var/www/linkedin-post-generator;
    index index.html;

    # The slow endpoint: long timeouts and rate limiting.
    location = /api/generate {
        limit_req zone=generate burst=3 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Everything else under /api (health check, docs).
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Vite puts a content hash in every asset file name, so they can be cached forever.
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }

    # Always re-check index.html so a new deploy shows up immediately.
    location = /index.html {
        add_header Cache-Control "no-cache";
    }

    # React Router: unknown paths such as /home and /output fall back to index.html.
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
```

What each part solves:

| Block | Problem it prevents |
|-------|---------------------|
| `proxy_read_timeout 300s` | nginx's default is 60 s. A slow three-agent run would be cut off with **504 Gateway Time-out**. |
| `limit_req` + `limit_req_status 429` | Stops one visitor (or a bot) from burning your Ollama quota. Excess requests get HTTP 429. |
| `try_files ... /index.html` | Without it, refreshing `/output` or opening `/home` directly returns **404**. |
| Separate `= /api/generate` block | Only the generate endpoint is rate-limited, so health checks are never blocked. |
| Cache headers | Fast repeat visits, while new deploys still appear immediately. |

### 9.2 Enable it

```bash
sudo ln -s /etc/nginx/sites-available/linkedin-post-generator /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default     # removes the "Welcome to nginx" page
sudo nginx -t                                     # must say "syntax is ok" and "test is successful"
sudo systemctl reload nginx
```

If `nginx -t` reports an error, it names the file and line. Fix it before reloading; a reload with
a broken config is refused and the old one keeps running.

---

## 10. Verify the deployment

### 10.1 On the server

```bash
curl -s http://127.0.0.1:8000/api/health     # backend directly:  {"status":"ok"}
curl -s http://localhost/api/health          # through nginx:     {"status":"ok"}
curl -sI http://localhost/output | head -1   # SPA fallback:      HTTP/1.1 200 OK
```

### 10.2 From your computer

1. Open **`http://<SERVER_IP>/home`** in your browser.
2. Enter a topic and click **Generate post**. You should land on `/output` within about a minute.
3. Refresh `/output`. The post should still be there, with no 404.
4. Optional API check from PowerShell:

```powershell
Invoke-RestMethod http://<SERVER_IP>/api/health
```

### 10.3 Reboot test

Make sure everything comes back on its own:

```bash
sudo reboot
```

Wait a minute, reconnect over SSH, and check:

```bash
systemctl is-active ollama linkedin-backend nginx     # three lines of "active"
```

> **Copy post** will show *"Copy failed"* on `http://<SERVER_IP>`. Browsers only allow clipboard
> access over HTTPS (or on localhost). Section 11 fixes this.

---

## 11. Add a domain and HTTPS

HTTPS encrypts traffic, makes the **Copy post** button work, and removes the browser's
"Not secure" warning. The simplest route needs a domain name.

### 11.1 Point the domain at the server

At your domain registrar or DNS provider, create an **A record**:

| Name | Type | Value |
|------|------|-------|
| `posts` (giving `posts.example.com`) or `@` for the bare domain | A | `<SERVER_IP>` |

DNS changes can take a few minutes to an hour. Check from PowerShell:

```powershell
Resolve-DnsName <YOUR_DOMAIN>     # should show <SERVER_IP>
```

### 11.2 Tell nginx the domain name

```bash
sudo sed -i 's/server_name _;/server_name <YOUR_DOMAIN>;/' /etc/nginx/sites-available/linkedin-post-generator
sudo nginx -t && sudo systemctl reload nginx
```

### 11.3 Get a free certificate (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <YOUR_DOMAIN>
```

Certbot asks for an email address (for expiry warnings) and to accept the terms. It then obtains a
certificate, adds HTTPS to your nginx config, and redirects HTTP to HTTPS.

### 11.4 Confirm automatic renewal

Certificates last 90 days, and the certbot package installs a timer that renews them. Test it once:

```bash
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
```

Your site is now at **`https://<YOUR_DOMAIN>/home`**.

---

## 12. Deploy updates

The workflow from now on: **change code on Windows → commit and push → run one script on the server.**

### 12.1 Create the deploy script (once, on the server)

```bash
tee ~/deploy.sh > /dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/home/ubuntu/LinkedIn_Content_generation
WEB_ROOT=/var/www/linkedin-post-generator

cd "$APP_DIR"
echo "==> Pulling latest code"
git pull --ff-only

echo "==> Backend"
.venv/bin/pip install -q -r requirement.txt
sudo systemctl restart linkedin-backend

echo "==> Frontend"
cd frontend
npm ci
npm run build
sudo rsync -a --delete dist/ "$WEB_ROOT/"

echo "==> Health check"
for i in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8000/api/health > /dev/null; then
    echo "Deploy finished, backend is healthy."
    exit 0
  fi
  sleep 1
done
echo "Backend did not come up. Check: journalctl -u linkedin-backend -n 50 --no-pager"
exit 1
EOF
chmod +x ~/deploy.sh
```

### 12.2 Each time you deploy

On Windows:

```powershell
git add <changed files>
git commit -m "Describe the change"
git push origin main
```

Then on the server:

```bash
ssh -i "<KEY_FILE>" ubuntu@<SERVER_IP>
~/deploy.sh
```

Edits to the prompt files (`backend/logic/prompts/*.md`) take effect on the next request, even
without a restart. The script restarts the backend anyway.

---

## 13. Operate the server

| Task | Command |
|------|---------|
| Is the backend running? | `systemctl status linkedin-backend --no-pager` |
| Follow backend logs live | `journalctl -u linkedin-backend -f` |
| Last 100 backend log lines | `journalctl -u linkedin-backend -n 100 --no-pager` |
| Restart the backend | `sudo systemctl restart linkedin-backend` |
| Ollama status / logs | `systemctl status ollama --no-pager` / `journalctl -u ollama -f` |
| Restart Ollama | `sudo systemctl restart ollama` |
| nginx error log | `sudo tail -f /var/log/nginx/error.log` |
| nginx access log (who visits) | `sudo tail -f /var/log/nginx/access.log` |
| Apply an nginx config change | `sudo nginx -t && sudo systemctl reload nginx` |
| Disk space / memory | `df -h` / `free -h` |
| Install OS updates | `sudo apt update && sudo apt upgrade -y` |

The backend logs every agent run (`Running writer agent`, ...) and the full error for every failed
request, so `journalctl -u linkedin-backend` is the first place to look when something breaks.

---

## 14. Security checklist

- [ ] **SSH** is open only to your IP. Update the rule (EC2 → Security Groups) when your home IP
      changes, rather than opening it to everyone. Ubuntu AMIs already disable password logins.
- [ ] **Only ports 80 and 443 are public.** FastAPI (8000) and Ollama (11434) listen on
      `127.0.0.1` only.
- [ ] **Rate limiting** on `/api/generate` is in place (section 9).
- [ ] **HTTPS** is enabled (section 11).
- [ ] **`.env`** has permissions `600` and is never committed to git.
- [ ] **Security updates:** Ubuntu installs security patches automatically (unattended-upgrades).
      Still run `sudo apt update && sudo apt upgrade -y` now and then, and reboot when
      `/var/run/reboot-required` exists.
- [ ] **Backup:** once everything works, create an AMI (EC2 → Instances → Actions → Image and
      templates → Create image) so you can rebuild the server in minutes.

### Optional: put the site behind a password

Useful for a private demo. Enable HTTPS first, because basic auth sends the password with every
request.

```bash
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd <username>     # prompts for a password
```

Add these two lines inside the `server { ... }` block of
`/etc/nginx/sites-available/linkedin-post-generator`:

```nginx
auth_basic "LinkedIn Post Generator";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Then `sudo nginx -t && sudo systemctl reload nginx`.

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| SSH: `UNPROTECTED PRIVATE KEY FILE` | Key file readable by other Windows users | Run the `icacls` command from section 3.1 |
| SSH hangs, then times out | Your IP changed, or the instance is stopped | Set the SSH rule's source to **My IP** again; check the instance state |
| Browser can't connect at all | Port 80 not open, or nginx not running | Check the security group; `systemctl status nginx` |
| "Welcome to nginx!" page | Default site still enabled | `sudo rm /etc/nginx/sites-enabled/default`, then reload nginx |
| **403 Forbidden** or **404** at `/` | nginx can't read the files, or they weren't copied | Re-run section 8.2; `ls /var/www/linkedin-post-generator` |
| **404** when refreshing `/output` | SPA fallback missing | Check the `location /` block with `try_files` (section 9) |
| **502 Bad Gateway** | Backend not running | `systemctl status linkedin-backend`; read `journalctl -u linkedin-backend -n 50` |
| **504 Gateway Time-out** | Generation took longer than `proxy_read_timeout` | Check `journalctl -u ollama`; raise the timeout in section 9 if runs are legitimately slow |
| *"Request failed with status 429."* | nginx rate limit reached | Wait a minute, or raise `rate=` / `burst=` in section 9 |
| *"Could not reach the Ollama server. Is it running?"* | Ollama service is down | `sudo systemctl restart ollama` |
| *"Model 'gpt-oss:20b-cloud' was not found on the Ollama server."* | Model not pulled on this server | `ollama pull gpt-oss:20b-cloud` |
| *"The model failed to generate a post."* with `401`/unauthorized in the backend logs | Server not signed in to ollama.com | `ollama signin` again (section 5.2) |
| Backend logs `ModuleNotFoundError: No module named 'app'` | Wrong `WorkingDirectory` in the service | It must be `.../LinkedIn_Content_generation/backend` (section 7.3) |
| `npm run build` prints `Killed` or "heap out of memory" | Not enough RAM | Add swap (section 4.3) or build on your PC (section 17) |
| `node -v` shows v18 | Ubuntu's own Node.js was installed | Redo section 4.2 |
| `certbot` fails the challenge | DNS doesn't point to the server yet, or port 80 is closed | Wait for DNS (`Resolve-DnsName`); check the security group |
| **Copy post** says *"Copy failed"* | Site served over plain HTTP | Enable HTTPS (section 11) |

---

## 16. Costs and cleanup

### What you pay for

Approximate on-demand prices in `us-east-1`. Prices vary by region and change over time, so check
the AWS pricing pages.

| Item | Approx. cost |
|------|--------------|
| t3.small instance | ~$0.021 per hour, ~$15 per month if always on |
| 20 GiB gp3 storage | ~$1.60 per month |
| Public IPv4 address (Elastic IP) | ~$0.005 per hour, ~$3.60 per month, charged even while unattached |
| Data transfer out | Small for a text app; AWS includes a free monthly allowance |
| Ollama cloud model usage | Depends on your ollama.com plan and its usage limits |

Set up an **AWS Budget** (Billing → Budgets) with an email alert, for example at $25 per month.

### Pausing vs. deleting

- **Stop** the instance: compute charges stop, but storage and the Elastic IP keep billing.
- **Delete everything** when you no longer need it:
  1. EC2 → Instances → select → **Terminate**
  2. EC2 → Elastic IPs → select → **Release**
  3. EC2 → AMIs / Snapshots → delete any backups you created
  4. Remove the DNS record at your domain provider

---

## 17. Alternatives

- **Build the frontend on your PC** (avoids installing Node.js on a small server). On Windows:
  `cd frontend; npm run build`, then upload with
  `scp -i "<KEY_FILE>" -r dist ubuntu@<SERVER_IP>:/tmp/dist`, and on the server run
  `sudo rsync -a --delete /tmp/dist/ /var/www/linkedin-post-generator/`.
- **Frontend on S3 + CloudFront, API on EC2:** this scales the static site better, but the browser
  then calls a different address. You must build with `VITE_API_BASE_URL=https://<api-domain>`
  and set `CORS_ORIGINS` on the backend to the frontend's address.
- **Docker:** packaging the backend and frontend as containers makes the server setup repeatable,
  and is a natural next step once this manual setup works.
