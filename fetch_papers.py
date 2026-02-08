"""
ArXiv AI Security Daily Digest

Autonomous newsletter pipeline:
- Fetches papers from ArXiv API
- Enriches with Semantic Scholar citation data
- Generates an HTML page published to GitHub Pages
- Generates an RSS feed anyone can subscribe to
- Optionally sends via Buttondown newsletter API (free, 100 subscribers)
- No email passwords required
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import json
import hashlib
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATEGORIES = ["cs.CR", "cs.AI", "cs.LG", "cs.CL", "cs.SE", "cs.MA", "cs.NI", "cs.OS"]

SEARCH_QUERIES = {
    "AI Red Teaming & Blue Teaming": [
        "red teaming",
        "blue teaming",
        "red team",
        "blue team",
        "adversarial testing",
        "AI safety evaluation",
        "PyRIT",
        "automated red teaming",
    ],
    "Prompt Injection & Jailbreaking": [
        "prompt injection",
        "jailbreak",
        "jailbreaking",
        "guardrail bypass",
        "safety alignment bypass",
        "indirect prompt injection",
        "XPIA",
    ],
    "LLM Security & Vulnerabilities": [
        "LLM security",
        "large language model security",
        "LLM vulnerability",
        "LLM attack",
        "adversarial prompt",
        "AI vulnerability",
        "data leakage LLM",
        "generative AI security",
    ],
    "Model Poisoning & Backdoors": [
        "model poisoning",
        "backdoor attack",
        "sleeper agent",
        "trojan model",
        "data poisoning",
        "training data attack",
    ],
    "Agentic AI Security": [
        "agentic AI security",
        "AI agent security",
        "multi-agent security",
        "tool-use vulnerability",
        "agent hijacking",
        "autonomous agent risk",
    ],
    "AI Safety & Robustness": [
        "AI safety",
        "model robustness",
        "adversarial robustness",
        "safety guardrail",
        "content filter bypass",
        "AI alignment",
        "responsible AI",
        "technical guardrail",
    ],
    "AI Ethics & Governance": [
        "AI ethics",
        "AI governance",
        "responsible AI",
        "AI accountability",
        "algorithmic fairness",
        "AI regulation",
        "AI oversight",
        "ethical AI",
        "AI transparency",
        "AI audit",
    ],
    "Sector-Specific AI Risks": [
        "financial AI risk",
        "AI financial services",
        "LLM finance",
        "AI manipulation",
        "manipulative AI",
        "AI advisory risk",
        "healthcare AI security",
        "AI fraud detection",
        "deepfake finance",
        "AI compliance",
    ],
    "LLM Efficiency & Optimization": [
        "LLM inference optimization",
        "KV cache",
        "LLM caching",
        "model compression",
        "speculative decoding",
        "LLM efficiency",
        "token pruning",
        "model distillation",
        "quantization LLM",
        "attention optimization",
        "GenCache",
        "structural pattern matching LLM",
    ],
    "Benchmarking & Evaluation": [
        "LLM benchmark security",
        "safety benchmark",
        "red teaming benchmark",
        "vulnerability scanner AI",
        "AI risk assessment",
    ],
    "Network Security": [
        "network intrusion detection",
        "network anomaly detection",
        "DDoS detection",
        "network traffic analysis",
        "firewall evasion",
        "network forensics",
        "zero trust network",
        "software defined networking security",
        "DNS security",
        "BGP security",
        "network threat detection",
        "deep packet inspection",
        "encrypted traffic analysis",
        "lateral movement detection",
        "network segmentation",
    ],
    "Operating System Security": [
        "operating system security",
        "kernel security",
        "kernel exploit",
        "privilege escalation",
        "container security",
        "sandbox escape",
        "memory safety",
        "buffer overflow",
        "return oriented programming",
        "OS hardening",
        "access control",
        "malware detection",
        "rootkit detection",
        "supply chain attack",
        "firmware security",
        "trusted execution environment",
    ],
}

# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

# High-value keywords: (phrase, weight)
# Title matches get 3x the weight of abstract matches.
RELEVANCE_KEYWORDS = [
    # Red teaming & automated security testing (weight 10)
    ("red teaming", 10), ("red team", 10), ("blue teaming", 10), ("blue team", 10),
    ("PyRIT", 10), ("automated red team", 10), ("adversarial testing", 8),

    # Jailbreaking & prompt injection (weight 10)
    ("jailbreak", 10), ("prompt injection", 10), ("guardrail bypass", 10),
    ("indirect prompt injection", 10), ("XPIA", 10), ("safety bypass", 9),

    # Generative AI security (weight 9)
    ("generative AI security", 9), ("LLM security", 9), ("LLM attack", 9),
    ("LLM vulnerability", 9), ("large language model security", 9),
    ("adversarial prompt", 8), ("data leakage", 8),

    # Model poisoning & backdoors (weight 8)
    ("model poisoning", 8), ("backdoor attack", 8), ("sleeper agent", 8),
    ("trojan model", 8), ("data poisoning", 8), ("training data attack", 8),

    # Agentic AI (weight 9)
    ("agentic AI", 9), ("AI agent security", 9), ("agent hijacking", 9),
    ("multi-agent security", 8), ("tool-use vulnerability", 8),

    # AI safety & guardrails (weight 8)
    ("AI safety", 8), ("safety guardrail", 8), ("content filter", 7),
    ("AI alignment", 7), ("robustness", 6), ("responsible AI", 7),

    # Ethics & governance (weight 7)
    ("AI ethics", 7), ("AI governance", 7), ("AI accountability", 7),
    ("algorithmic fairness", 6), ("AI regulation", 7), ("AI oversight", 7),
    ("AI audit", 7), ("AI transparency", 6),

    # Financial / sector risks (weight 8)
    ("financial AI", 8), ("AI financial services", 8), ("manipulative", 7),
    ("AI advisory", 7), ("AI fraud", 7), ("deepfake", 7), ("AI compliance", 7),

    # LLM efficiency & optimization (weight 7)
    ("KV cache", 7), ("LLM caching", 7), ("inference optimization", 7),
    ("model compression", 6), ("speculative decoding", 7), ("GenCache", 8),
    ("token pruning", 6), ("model distillation", 6), ("quantization", 5),
    ("attention optimization", 6),

    # Network & OS security (weight 5)
    ("intrusion detection", 5), ("DDoS", 5), ("zero trust", 5),
    ("kernel security", 5), ("privilege escalation", 5), ("container security", 5),
    ("supply chain attack", 6), ("malware detection", 5),
]


def compute_relevance(paper: dict) -> int:
    """Score a paper 0-100 based on keyword matches in title and abstract."""
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    score = 0

    for phrase, weight in RELEVANCE_KEYWORDS:
        phrase_lower = phrase.lower()
        if phrase_lower in title:
            score += weight * 3  # title matches worth 3x
        if phrase_lower in abstract:
            score += weight

    # Cap at 100
    return min(score, 100)

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))
MAX_RESULTS_PER_QUERY = int(os.environ.get("MAX_RESULTS", "50"))
SEEN_PAPERS_FILE = Path("seen_papers.json")
OUTPUT_DIR = Path("public")
ARCHIVE_DIR = OUTPUT_DIR / "archive"

# Site config (set via env vars or defaults)
SITE_TITLE = os.environ.get("SITE_TITLE", "AI Security Research Digest")
SITE_URL = os.environ.get("SITE_URL", "https://ek0212.github.io/arxiv-ai-security-digest")
SITE_DESCRIPTION = os.environ.get(
    "SITE_DESCRIPTION",
    "Daily digest of ArXiv papers on AI security, red/blue teaming, prompt injection, "
    "jailbreaking, model poisoning, AI ethics, LLM efficiency, sector-specific risks, "
    "network security, and OS security. Sorted by relevance and citation count."
)

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
S2_API = "https://api.semanticscholar.org/graph/v1/paper"


# ---------------------------------------------------------------------------
# ArXiv API
# ---------------------------------------------------------------------------

def build_query(keywords: list[str], categories: list[str]) -> str:
    kw_parts = []
    for kw in keywords:
        if " " in kw:
            kw_parts.append(f'all:"{kw}"')
        else:
            kw_parts.append(f"all:{kw}")
    kw_query = "+OR+".join(kw_parts)
    cat_parts = [f"cat:{c}" for c in categories]
    cat_query = "+OR+".join(cat_parts)
    return f"({kw_query})+AND+({cat_query})"


def fetch_arxiv(query: str, max_results: int = 50) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ArxivDigest/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  [ERROR] Failed to fetch from ArXiv: {e}")
        return []

    root = ET.fromstring(data)
    papers = []

    for entry in root.findall("atom:entry", ARXIV_NS):
        title_el = entry.find("atom:title", ARXIV_NS)
        summary_el = entry.find("atom:summary", ARXIV_NS)
        published_el = entry.find("atom:published", ARXIV_NS)
        updated_el = entry.find("atom:updated", ARXIV_NS)

        arxiv_id = ""
        arxiv_id_raw = ""
        pdf_link = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            href = link.get("href", "")
            if link.get("title") == "pdf":
                pdf_link = href
            elif "abs" in href:
                arxiv_id = href

        id_el = entry.find("atom:id", ARXIV_NS)
        if id_el is not None and id_el.text:
            match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", id_el.text)
            if match:
                arxiv_id_raw = match.group(1)

        cats = [c.get("term", "") for c in entry.findall("atom:category", ARXIV_NS)]
        authors = []
        for author in entry.findall("atom:author", ARXIV_NS):
            name_el = author.find("atom:name", ARXIV_NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else "No title"
        abstract = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
        published = published_el.text.strip() if published_el is not None and published_el.text else ""
        updated = updated_el.text.strip() if updated_el is not None and updated_el.text else ""

        papers.append({
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published,
            "updated": updated,
            "arxiv_url": arxiv_id,
            "arxiv_id_raw": arxiv_id_raw,
            "pdf_url": pdf_link,
            "categories": cats,
            "citation_count": 0,
            "influential_citations": 0,
            "s2_url": "",
        })

    return papers


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

def enrich_with_citations(papers: list[dict]) -> list[dict]:
    if not papers:
        return papers

    arxiv_ids = [p["arxiv_id_raw"] for p in papers if p.get("arxiv_id_raw")]
    if not arxiv_ids:
        print("  No ArXiv IDs available for citation lookup")
        return papers

    id_to_papers = {}
    for p in papers:
        if p.get("arxiv_id_raw"):
            id_to_papers[p["arxiv_id_raw"]] = p

    batch_url = f"{S2_API}/batch"
    batch_size = 100
    total_enriched = 0

    for i in range(0, len(arxiv_ids), batch_size):
        batch = arxiv_ids[i:i + batch_size]
        payload = json.dumps({"ids": [f"ArXiv:{aid}" for aid in batch]}).encode("utf-8")
        params = urllib.parse.urlencode({"fields": "citationCount,influentialCitationCount,url"})
        url = f"{batch_url}?{params}"

        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "ArxivDigest/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                results = json.loads(resp.read())

            for j, result in enumerate(results):
                if result is None:
                    continue
                aid = batch[j]
                if aid in id_to_papers:
                    p = id_to_papers[aid]
                    p["citation_count"] = result.get("citationCount", 0) or 0
                    p["influential_citations"] = result.get("influentialCitationCount", 0) or 0
                    p["s2_url"] = result.get("url", "")
                    total_enriched += 1

        except Exception as e:
            print(f"  [WARN] Batch S2 lookup failed: {e}")
            for aid in batch:
                if aid not in id_to_papers:
                    continue
                try:
                    params = urllib.parse.urlencode({"fields": "citationCount,influentialCitationCount,url"})
                    single_url = f"{S2_API}/ArXiv:{aid}?{params}"
                    req = urllib.request.Request(single_url, headers={"User-Agent": "ArxivDigest/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        result = json.loads(resp.read())
                    p = id_to_papers[aid]
                    p["citation_count"] = result.get("citationCount", 0) or 0
                    p["influential_citations"] = result.get("influentialCitationCount", 0) or 0
                    p["s2_url"] = result.get("url", "")
                    total_enriched += 1
                except Exception:
                    pass
                time.sleep(0.7)

        if i + batch_size < len(arxiv_ids):
            time.sleep(1)

    print(f"  Enriched {total_enriched}/{len(papers)} papers with citation data")
    return papers


def score_and_sort_papers(papers: list[dict]) -> list[dict]:
    """Score each paper for relevance, then sort by relevance first, citations second."""
    for p in papers:
        p["relevance_score"] = compute_relevance(p)
    return sorted(
        papers,
        key=lambda p: (
            p.get("relevance_score", 0),
            p.get("influential_citations", 0),
            p.get("citation_count", 0),
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Filtering & dedup
# ---------------------------------------------------------------------------

def is_recent(paper: dict, days: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for date_str in [paper.get("updated", ""), paper.get("published", "")]:
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt >= cutoff:
                return True
        except ValueError:
            continue
    return False


def paper_id(paper: dict) -> str:
    return hashlib.md5(paper["title"].lower().encode()).hexdigest()


def load_seen() -> set:
    if SEEN_PAPERS_FILE.exists():
        try:
            return set(json.loads(SEEN_PAPERS_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    seen_list = list(seen)[-5000:]
    SEEN_PAPERS_FILE.write_text(json.dumps(seen_list))


# ---------------------------------------------------------------------------
# HTML generation (GitHub Pages site)
# ---------------------------------------------------------------------------

def metrics_badge_html(paper: dict) -> str:
    """Render relevance score and citation count as visible badges."""
    parts = []

    # Relevance score badge
    rs = paper.get("relevance_score", 0)
    if rs >= 50:
        rs_cls = "badge-relevance-high"
    elif rs >= 25:
        rs_cls = "badge-relevance-med"
    elif rs > 0:
        rs_cls = "badge-relevance-low"
    else:
        rs_cls = "badge-relevance-none"
    parts.append(f'<span class="badge {rs_cls}">Relevance: {rs}/100</span>')

    # Citation count badge
    cc = paper.get("citation_count", 0)
    ic = paper.get("influential_citations", 0)
    if cc == 0 and ic == 0:
        parts.append('<span class="badge badge-new">Citations: 0 (new)</span>')
    else:
        if cc > 0:
            cls = "badge-high" if cc >= 10 else "badge-med" if cc >= 3 else "badge-low"
            parts.append(f'<span class="badge {cls}">Citations: {cc}</span>')
        if ic > 0:
            parts.append(f'<span class="badge badge-influential">{ic} influential</span>')

    return " ".join(parts)


def generate_site(papers_by_topic: dict[str, list[dict]], date_str: str, iso_date: str):
    """Generate the full static site: index.html, archive page, and RSS feed."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(len(ps) for ps in papers_by_topic.values())

    # --- Shared CSS ---
    css = """
:root {
    --bg: #f8f9fa; --surface: #fff; --text: #1a1a1a; --muted: #666;
    --accent: #0f3460; --accent-light: #e8edf3; --border: #e0e0e0;
    --green-bg: #e6f4e6; --green: #2d6a2d; --yellow-bg: #f5f5dc; --yellow: #5a5a00;
    --orange-bg: #fff3e0; --orange: #e65100;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 760px; margin: 0 auto; padding: 20px; color: var(--text);
       background: var(--bg); line-height: 1.6; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
           color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }
.header h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
.header p { opacity: 0.85; font-size: 14px; }
.header .subscribe-row { margin-top: 16px; display: flex; gap: 12px; flex-wrap: wrap; }
.header .subscribe-row a { color: white; background: rgba(255,255,255,0.15);
    padding: 6px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
    transition: background 0.2s; }
.header .subscribe-row a:hover { background: rgba(255,255,255,0.3); text-decoration: none; }
.nav { display: flex; gap: 16px; margin-bottom: 20px; font-size: 14px; }
.sort-note { font-size: 12px; color: var(--muted); margin-bottom: 20px;
             padding: 8px 12px; background: var(--surface); border-left: 3px solid var(--accent);
             border-radius: 4px; }
.topic { margin-bottom: 28px; }
.topic-header { font-size: 16px; font-weight: 700; color: var(--accent);
                border-bottom: 2px solid var(--accent); padding-bottom: 6px; margin-bottom: 14px; }
.paper { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
         padding: 16px; margin-bottom: 12px; }
.paper-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.paper-meta { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.paper-citations { margin-bottom: 8px; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
         display: inline-block; margin-right: 4px; }
.badge-new { background: #f0f0f0; color: #999; }
.badge-low { background: #f0f0f0; color: #666; }
.badge-med { background: var(--yellow-bg); color: var(--yellow); }
.badge-high { background: var(--green-bg); color: var(--green); }
.badge-influential { background: var(--orange-bg); color: var(--orange); }
.badge-relevance-high { background: #e3f2fd; color: #0d47a1; }
.badge-relevance-med { background: #e8eaf6; color: #283593; }
.badge-relevance-low { background: #f3e5f5; color: #6a1b9a; }
.badge-relevance-none { background: #f0f0f0; color: #999; }
.paper-abstract { font-size: 13px; color: #333; }
.paper-cats { font-size: 11px; color: #888; margin-top: 8px; }
.paper-cats span { background: var(--accent-light); padding: 2px 8px; border-radius: 4px;
                   margin-right: 4px; display: inline-block; margin-bottom: 4px; }
.paper-links { font-size: 12px; margin-top: 8px; }
.paper-links a { margin-right: 12px; }
.footer { text-align: center; font-size: 12px; color: #999; margin-top: 30px;
          padding-top: 16px; border-top: 1px solid var(--border); }
.no-papers { color: var(--muted); font-style: italic; padding: 12px; }
.archive-list { list-style: none; }
.archive-list li { padding: 8px 0; border-bottom: 1px solid var(--border); }
.archive-list li:last-child { border-bottom: none; }
"""

    # --- Build paper cards HTML (reused in index and archive) ---
    def render_papers_html(papers_by_topic_sorted):
        html = ""
        for topic, papers in papers_by_topic_sorted.items():
            if not papers:
                continue
            html += f'<div class="topic"><div class="topic-header">{topic} ({len(papers)})</div>\n'
            for p in papers:
                authors_str = ", ".join(p["authors"][:5])
                if len(p["authors"]) > 5:
                    authors_str += f' + {len(p["authors"]) - 5} more'
                cats_html = "".join(f'<span>{c}</span>' for c in p["categories"][:5])
                abstract_short = p["abstract"][:500]
                if len(p["abstract"]) > 500:
                    abstract_short += "..."
                badge = metrics_badge_html(p)
                links = f'<a href="{p["arxiv_url"]}">ArXiv</a>'
                if p.get("pdf_url"):
                    links += f' <a href="{p["pdf_url"]}">PDF</a>'
                if p.get("s2_url"):
                    links += f' <a href="{p["s2_url"]}">Semantic Scholar</a>'

                html += f"""<div class="paper">
  <div class="paper-title"><a href="{p['arxiv_url']}">{p['title']}</a></div>
  <div class="paper-meta">{authors_str} &middot; {p['published'][:10]}</div>
  <div class="paper-citations">{badge}</div>
  <div class="paper-abstract">{abstract_short}</div>
  <div class="paper-cats">{cats_html}</div>
  <div class="paper-links">{links}</div>
</div>\n"""
            html += "</div>\n"
        return html

    # Score and sort papers within each topic (relevance first, then citations)
    sorted_topics = {t: score_and_sort_papers(ps) for t, ps in papers_by_topic.items()}
    papers_html = render_papers_html(sorted_topics)

    if total == 0:
        papers_html = '<p class="no-papers">No new papers found today. Check back tomorrow.</p>'

    # --- index.html ---
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SITE_TITLE}</title>
<meta name="description" content="{SITE_DESCRIPTION}">
<link rel="alternate" type="application/rss+xml" title="{SITE_TITLE}" href="{SITE_URL}/feed.xml">
<style>{css}</style>
</head>
<body>
<div class="header">
  <h1>{SITE_TITLE}</h1>
  <p>{date_str} &middot; {total} new paper{"s" if total != 1 else ""}</p>
  <div class="subscribe-row">
    <a href="{SITE_URL}/feed.xml">&#128227; RSS Feed</a>
    <a href="https://github.com/ek0212/arxiv-ai-security-digest">&#11088; GitHub</a>
  </div>
</div>
<nav class="nav">
  <a href="{SITE_URL}/">Today</a>
  <a href="{SITE_URL}/archive/">Archive</a>
</nav>
<div class="sort-note">
  Sorted by relevance score (keyword match to priority topics), then by citation count via Semantic Scholar.
</div>
{papers_html}
<div class="footer">
  Updated daily via GitHub Actions &middot;
  Papers from <a href="https://arxiv.org">arxiv.org</a> &middot;
  Citations from <a href="https://www.semanticscholar.org">Semantic Scholar</a><br>
  Subscribe via <a href="{SITE_URL}/feed.xml">RSS</a>
</div>
</body>
</html>"""

    (OUTPUT_DIR / "index.html").write_text(index_html)
    print(f"Generated {OUTPUT_DIR / 'index.html'}")

    # --- Archive page for today ---
    archive_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SITE_TITLE} - {date_str}</title>
<style>{css}</style>
</head>
<body>
<div class="header">
  <h1>{SITE_TITLE}</h1>
  <p>{date_str} &middot; {total} papers</p>
</div>
<nav class="nav">
  <a href="{SITE_URL}/">&larr; Latest</a>
  <a href="{SITE_URL}/archive/">Archive</a>
</nav>
{papers_html}
<div class="footer">
  <a href="{SITE_URL}/">Back to latest</a>
</div>
</body>
</html>"""

    archive_file = ARCHIVE_DIR / f"{iso_date}.html"
    archive_file.write_text(archive_page)
    print(f"Generated {archive_file}")

    # --- Archive index ---
    archive_files = sorted(ARCHIVE_DIR.glob("*.html"), reverse=True)
    archive_links = ""
    for af in archive_files[:90]:  # keep last 90 days
        d = af.stem
        try:
            nice_date = datetime.strptime(d, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            nice_date = d
        archive_links += f'<li><a href="{SITE_URL}/archive/{af.name}">{nice_date}</a></li>\n'

    archive_index = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SITE_TITLE} - Archive</title>
<style>{css}</style>
</head>
<body>
<div class="header">
  <h1>{SITE_TITLE}</h1>
  <p>Archive</p>
</div>
<nav class="nav">
  <a href="{SITE_URL}/">&larr; Latest</a>
</nav>
<ul class="archive-list">
{archive_links}
</ul>
<div class="footer">
  <a href="{SITE_URL}/">Back to latest</a>
</div>
</body>
</html>"""

    (ARCHIVE_DIR / "index.html").write_text(archive_index)
    print(f"Generated {ARCHIVE_DIR / 'index.html'}")

    # --- RSS feed ---
    generate_rss(papers_by_topic, sorted_topics, date_str, iso_date)

    # --- Buttondown (optional) ---
    buttondown_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if buttondown_key and total > 0:
        send_buttondown(buttondown_key, papers_html, date_str, total, css)


def xml_escape(text: str) -> str:
    """Escape text for safe inclusion in XML."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def generate_rss(papers_by_topic, sorted_topics, date_str, iso_date):
    """Generate RSS 2.0 feed."""
    now_rfc822 = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    items = ""
    for topic, papers in sorted_topics.items():
        topic_escaped = xml_escape(topic)
        for p in papers:
            abstract_short = p["abstract"][:300]
            if len(p["abstract"]) > 300:
                abstract_short += "..."
            abstract_escaped = xml_escape(abstract_short)
            title_escaped = xml_escape(p["title"])
            cc = p.get("citation_count", 0)
            rs = p.get("relevance_score", 0)
            cite_note = f" [{cc} citations]" if cc > 0 else ""
            rel_note = f" [rel:{rs}]"

            items += f"""    <item>
      <title>[{topic_escaped}]{cite_note}{rel_note} {title_escaped}</title>
      <link>{p['arxiv_url']}</link>
      <guid isPermaLink="true">{p['arxiv_url']}</guid>
      <description>{abstract_escaped}</description>
      <pubDate>{now_rfc822}</pubDate>
      <category>{topic_escaped}</category>
    </item>
"""

    title_escaped = xml_escape(SITE_TITLE)
    desc_escaped = xml_escape(SITE_DESCRIPTION)

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{title_escaped}</title>
    <link>{SITE_URL}</link>
    <description>{desc_escaped}</description>
    <language>en-us</language>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
{items}  </channel>
</rss>"""

    (OUTPUT_DIR / "feed.xml").write_text(feed)
    print(f"Generated {OUTPUT_DIR / 'feed.xml'}")


# ---------------------------------------------------------------------------
# Buttondown newsletter API (optional, free tier = 100 subscribers)
# ---------------------------------------------------------------------------

def send_buttondown(api_key: str, papers_html: str, date_str: str, total: int, css: str):
    """Send newsletter via Buttondown API. No email password needed, just an API key."""
    url = "https://api.buttondown.com/v1/emails"

    email_body = f"""<style>{css}</style>
<div style="max-width:700px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<h1 style="color:#0f3460;">AI Security Research Digest</h1>
<p style="color:#666;">{date_str} &middot; {total} new papers</p>
<hr style="border:1px solid #e0e0e0;margin:16px 0;">
{papers_html}
<hr style="border:1px solid #e0e0e0;margin:16px 0;">
<p style="font-size:12px;color:#999;text-align:center;">
  <a href="{SITE_URL}">View on web</a> &middot;
  <a href="{SITE_URL}/feed.xml">RSS feed</a>
</p>
</div>"""

    payload = json.dumps({
        "subject": f"AI Security Digest: {total} new papers ({date_str})",
        "body": email_body,
        "status": "draft",  # change to "about_to_send" for auto-send
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"Buttondown: Created email draft (id: {result.get('id', 'unknown')})")
    except Exception as e:
        print(f"[WARN] Buttondown API failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"ArXiv AI Security Digest - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Lookback: {LOOKBACK_DAYS} days")
    print()

    seen = load_seen()
    papers_by_topic: dict[str, list[dict]] = {}
    all_new_ids = set()

    for topic, keywords in SEARCH_QUERIES.items():
        print(f"Searching: {topic} ({len(keywords)} keywords)...")
        query = build_query(keywords, CATEGORIES)
        raw_papers = fetch_arxiv(query, MAX_RESULTS_PER_QUERY)
        print(f"  Fetched {len(raw_papers)} results from ArXiv")

        new_papers = []
        for p in raw_papers:
            pid = paper_id(p)
            if pid in seen or pid in all_new_ids:
                continue
            if not is_recent(p, LOOKBACK_DAYS):
                continue
            new_papers.append(p)
            all_new_ids.add(pid)

        if new_papers:
            print(f"  Looking up citations for {len(new_papers)} papers...")
            new_papers = enrich_with_citations(new_papers)

        papers_by_topic[topic] = new_papers
        print(f"  {len(new_papers)} new papers after filtering")

    total = sum(len(ps) for ps in papers_by_topic.values())
    print(f"\nTotal new papers: {total}")

    all_papers = [p for ps in papers_by_topic.values() for p in ps]
    cited_papers = [p for p in all_papers if p.get("citation_count", 0) > 0]
    if cited_papers:
        cited_papers.sort(key=lambda p: p.get("citation_count", 0), reverse=True)
        print(f"\nTop cited papers:")
        for p in cited_papers[:5]:
            print(f"  [{p['citation_count']} citations] {p['title'][:80]}")

    seen.update(all_new_ids)
    save_seen(seen)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")
    iso_date = now.strftime("%Y-%m-%d")

    generate_site(papers_by_topic, date_str, iso_date)
    print("\nDone.")


if __name__ == "__main__":
    main()
