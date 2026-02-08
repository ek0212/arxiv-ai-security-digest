# ArXiv AI Security Daily Digest

An autonomous, free newsletter pipeline that publishes daily ArXiv papers on AI security topics.

**No email passwords. No manual intervention. Multiple subscribers supported.**

## How People Subscribe

There are two ways for people to get your digest:

1. **RSS feed** (unlimited subscribers, zero cost): Anyone can add your feed URL to their RSS reader (Feedly, Inoreader, Thunderbird, etc.)
2. **Buttondown email newsletter** (optional, free for up to 100 subscribers): People sign up on your Buttondown page and get the digest in their inbox

Both options are free and require no email passwords or SMTP configuration.

## What It Does Every Day

1. GitHub Actions triggers at 8 AM UTC
2. Fetches new papers from ArXiv across 9 topic areas
3. Looks up citation counts via Semantic Scholar
4. Sorts papers by citation count within each topic
5. Generates a static website and deploys it to GitHub Pages
6. Generates an RSS feed
7. (Optional) Creates a Buttondown newsletter draft

## Topic Areas

| Topic | Example Keywords |
|-------|-----------------|
| AI Red Teaming & Blue Teaming | red teaming, blue teaming, adversarial testing |
| Prompt Injection & Jailbreaking | prompt injection, jailbreak, XPIA, guardrail bypass |
| LLM Security & Vulnerabilities | LLM security, adversarial prompt, AI vulnerability |
| Model Poisoning & Backdoors | model poisoning, backdoor attack, sleeper agent, trojan |
| Agentic AI Security | agent security, multi-agent security, agent hijacking |
| AI Safety & Robustness | AI safety, adversarial robustness, safety guardrail, AI alignment |
| Benchmarking & Evaluation | safety benchmark, red teaming benchmark, vulnerability scanner |
| Network Security | intrusion detection, DDoS, traffic analysis, zero trust, BGP, DNS |
| Operating System Security | kernel security, privilege escalation, container security, malware, rootkit |

## Setup (10 minutes)

### 1. Create the repo

Click "Use this template" or fork this repo on GitHub.

### 2. Enable GitHub Pages

Go to your repo > Settings > Pages:
- Source: **GitHub Actions**

That's it. Your site will be live at `https://ek0212.github.io/arxiv-ai-security-digest` after the first run.

### 3. Update the site URL

The workflow automatically sets `SITE_URL` based on your GitHub username and repo name. If you use a custom domain, update the `SITE_URL` env var in `.github/workflows/daily_digest.yml`.

### 4. Run it

Go to Actions > "Daily AI Security ArXiv Digest" > "Run workflow"

After a few minutes:
- Your site will be live at `https://ek0212.github.io/arxiv-ai-security-digest`
- Your RSS feed will be at `https://ek0212.github.io/arxiv-ai-security-digest/feed.xml`

### 5. (Optional) Set up Buttondown for email subscribers

If you want people to subscribe via email:

1. Create a free account at [buttondown.com](https://buttondown.com) (free for up to 100 subscribers)
2. Go to Settings > API and copy your API key
3. In your GitHub repo, go to Settings > Secrets > Actions > New repository secret
4. Add `BUTTONDOWN_API_KEY` with your API key

By default, Buttondown drafts are created in "draft" status so you can review before sending. To auto-send, change `"status": "draft"` to `"status": "about_to_send"` in `fetch_papers.py`.

Share your Buttondown signup page with people who want email delivery.

## How It Stays Autonomous

- **No email passwords needed.** GitHub Pages serves the site. RSS is a static XML file. Buttondown handles email delivery via their API key (not your email credentials).
- **No manual steps.** The GitHub Action runs on a cron schedule and commits its own state.
- **Deduplication is automatic.** `seen_papers.json` is committed back to the repo after each run to prevent duplicate papers.
- **Archive builds automatically.** Each day's digest is saved to `/archive/YYYY-MM-DD.html` with an index page.

## Configuration

### Change the schedule

Edit `.github/workflows/daily_digest.yml`:

```yaml
schedule:
  - cron: '0 8 * * *'  # 8 AM UTC daily
```

Useful cron values:
- `'0 13 * * *'` = 8 AM EST
- `'0 15 * * *'` = 8 AM PST
- `'0 8 * * 1-5'` = Weekdays only

### Change the lookback window

Set `LOOKBACK_DAYS` in the workflow file. Default is `7`.

### Add or remove topics

Edit `SEARCH_QUERIES` in `fetch_papers.py`.

### Add ArXiv categories

Edit `CATEGORIES` in `fetch_papers.py`. See https://arxiv.org/category_taxonomy for the full list.

## Project Structure

```
.
├── .github/workflows/daily_digest.yml   # GitHub Actions cron job
├── fetch_papers.py                       # Main script
├── seen_papers.json                      # Dedup state (auto-updated)
├── public/                               # Generated site (auto-updated)
│   ├── index.html                        # Latest digest
│   ├── feed.xml                          # RSS feed
│   └── archive/                          # Past digests
│       ├── index.html                    # Archive listing
│       └── 2026-02-08.html              # Daily snapshots
└── README.md
```

## Costs

| Service | Free Tier | Limit |
|---------|-----------|-------|
| GitHub Actions | 2,000 min/month | Each run takes ~2 min |
| GitHub Pages | Unlimited | 1 GB storage, 100 GB bandwidth/month |
| ArXiv API | Unlimited | No key required |
| Semantic Scholar API | 100 req/min | No key required |
| Buttondown (optional) | 100 subscribers | Free tier |

Total cost: **$0**

## License

MIT
