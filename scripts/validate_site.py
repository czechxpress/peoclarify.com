#!/usr/bin/env python3
"""
peoclarify.com site validator
Runs in CI on every push to main and every PR.
Exits non-zero on hard failures, prints warnings for soft issues.

12 categories of checks (ported from leavepeo build):
 1. Single DOCTYPE per HTML file
 2. GA tracking present (warn only until GA_ID is wired)
 3. Canonical URLs are extension-less
 4. Sitemap covers every public HTML page
 5. Blog index links every blog post
 6. _redirects covers every .html file (extension-less rewrite)
 7. No em dashes in title, meta description, or og/twitter titles
 8. Contact info in footer (assessment link or peter.sustr email)
 9. target=_blank links carry rel=noopener
10. Exactly one H1 per page
11. Exactly one canonical link per page
12. No obviously missing closing tags (html, body, head)
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GA_ID_EXPECTED = "G-KHSV52SZF6"  # GA4 Measurement ID set 2026-04-29

errors = []
warnings = []

def err(msg):
    errors.append(msg)

def warn(msg):
    warnings.append(msg)

def list_html_files():
    files = []
    for path in ROOT.glob("*.html"):
        files.append(path)
    for path in (ROOT / "blog").glob("*.html"):
        files.append(path)
    return sorted(files)

def read(path):
    return path.read_text(encoding="utf-8", errors="replace")

# ---------- per-file checks ----------
def check_doctype(path, body):
    count = len(re.findall(r"<!doctype\s+html", body, re.IGNORECASE))
    if count == 0:
        err(f"{path.relative_to(ROOT)}: missing <!DOCTYPE html>")
    elif count > 1:
        err(f"{path.relative_to(ROOT)}: {count} DOCTYPE declarations (expected 1)")

def check_canonical(path, body):
    canonicals = re.findall(r'rel="canonical"\s+href="([^"]+)"', body)
    # 404 pages are noindex and don't need a canonical
    if path.name == "404.html":
        if len(canonicals) > 1:
            err(f"{path.relative_to(ROOT)}: {len(canonicals)} canonical links (expected 0 or 1 on 404)")
        for c in canonicals:
            if c.endswith(".html"):
                err(f"{path.relative_to(ROOT)}: canonical ends with .html ({c})")
        return
    if len(canonicals) == 0:
        err(f"{path.relative_to(ROOT)}: missing canonical link")
        return
    if len(canonicals) > 1:
        err(f"{path.relative_to(ROOT)}: {len(canonicals)} canonical links (expected 1)")
    for c in canonicals:
        if c.endswith(".html"):
            err(f"{path.relative_to(ROOT)}: canonical ends with .html ({c})")

def check_h1(path, body):
    h1s = re.findall(r"<h1\b", body, re.IGNORECASE)
    if len(h1s) == 0:
        err(f"{path.relative_to(ROOT)}: no <h1> found")
    elif len(h1s) > 1:
        err(f"{path.relative_to(ROOT)}: {len(h1s)} <h1> tags (expected 1)")

def check_em_dashes_in_meta(path, body):
    title_match = re.search(r"<title>([^<]*)</title>", body)
    if title_match and "—" in title_match.group(1):
        err(f"{path.relative_to(ROOT)}: em dash in <title>")
    for tag in ("description", "og:title", "og:description", "twitter:title", "twitter:description"):
        for m in re.finditer(rf'(?:name|property)="{re.escape(tag)}"\s+content="([^"]+)"', body):
            if "—" in m.group(1):
                err(f"{path.relative_to(ROOT)}: em dash in meta {tag}")

def check_target_blank(path, body):
    for m in re.finditer(r'<a\b[^>]*target="_blank"[^>]*>', body):
        tag = m.group(0)
        if "rel=" not in tag or "noopener" not in tag:
            err(f"{path.relative_to(ROOT)}: target=_blank link missing rel=noopener: {tag[:120]}")

def check_closing_tags(path, body):
    for tag in ("html", "head", "body"):
        if f"</{tag}>" not in body.lower():
            err(f"{path.relative_to(ROOT)}: missing closing </{tag}>")

# Tracks pages missing GA so we emit one summary line instead of 25 warnings
_ga_missing_pages = []

def check_ga(path, body):
    if not GA_ID_EXPECTED:
        if "gtag(" not in body and "googletagmanager" not in body:
            _ga_missing_pages.append(str(path.relative_to(ROOT)))
        return
    if GA_ID_EXPECTED not in body:
        err(f"{path.relative_to(ROOT)}: GA tracking missing or wrong ID (expected {GA_ID_EXPECTED})")

def check_footer_contact(path, body):
    has_assessment = "/assessment" in body
    has_email = "peter.sustr" in body or "petersustr" in body
    if not (has_assessment or has_email):
        warn(f"{path.relative_to(ROOT)}: no assessment link or contact email in body")

# ---------- whole-site checks ----------
def check_sitemap_coverage(html_files):
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        err("sitemap.xml missing")
        return
    sm_body = read(sitemap)
    listed = set(re.findall(r"<loc>([^<]+)</loc>", sm_body))
    listed_paths = set()
    for url in listed:
        m = re.match(r"https?://[^/]+(/.*)$", url)
        if m:
            listed_paths.add(m.group(1).rstrip("/") or "/")
    expected_paths = set()
    for f in html_files:
        rel = f.relative_to(ROOT)
        if str(rel) == "404.html":
            continue
        if str(rel) == "index.html":
            expected_paths.add("/")
        elif str(rel) == "blog/index.html":
            expected_paths.add("/blog")
        elif rel.parts[0] == "blog":
            expected_paths.add(f"/blog/{rel.stem}")
        else:
            expected_paths.add(f"/{rel.stem}")
    missing = expected_paths - listed_paths
    extra = {p for p in listed_paths if p not in expected_paths and p not in ("/blog", "/blog/")}
    for p in sorted(missing):
        err(f"sitemap.xml missing entry for {p}")
    for p in sorted(extra):
        warn(f"sitemap.xml lists {p} but no source HTML found")

def check_blog_index_coverage(html_files):
    blog_index = ROOT / "blog" / "index.html"
    if not blog_index.exists():
        err("blog/index.html missing")
        return
    body = read(blog_index)
    blog_posts = [f for f in html_files if f.relative_to(ROOT).parts[0] == "blog" and f.name != "index.html"]
    for post in blog_posts:
        slug = post.stem
        if f"/blog/{slug}" not in body and f"{slug}.html" not in body:
            err(f"blog/index.html does not link to /blog/{slug}")

def check_redirect_coverage(html_files):
    redirects_path = ROOT / "_redirects"
    if not redirects_path.exists():
        err("_redirects missing")
        return
    body = read(redirects_path)
    for f in html_files:
        rel = f.relative_to(ROOT)
        if str(rel) in ("404.html", "index.html", "blog/index.html"):
            continue
        if rel.parts[0] == "blog":
            target = f"/blog/{rel.stem}.html"
        else:
            target = f"/{rel.stem}.html"
        if target not in body:
            warn(f"_redirects has no entry rewriting {target} to extension-less form")

# ---------- main ----------
def main():
    html_files = list_html_files()
    if not html_files:
        err("no HTML files found")
    for path in html_files:
        body = read(path)
        check_doctype(path, body)
        check_canonical(path, body)
        check_h1(path, body)
        check_em_dashes_in_meta(path, body)
        check_target_blank(path, body)
        check_closing_tags(path, body)
        check_ga(path, body)
        check_footer_contact(path, body)
    check_sitemap_coverage(html_files)
    check_blog_index_coverage(html_files)
    check_redirect_coverage(html_files)

    if _ga_missing_pages and not GA_ID_EXPECTED:
        print(f"NOTE: GA tracking not yet provisioned. {len(_ga_missing_pages)} pages have no gtag snippet.")
        print("      Set GA_ID_EXPECTED in scripts/validate_site.py once the GA4 Measurement ID is created;")
        print("      validator will then HARD-FAIL any page missing the ID.")
        print()
    if warnings:
        print(f"--- {len(warnings)} warnings ---")
        for w in warnings:
            print(f"  WARN: {w}")
    if errors:
        print(f"--- {len(errors)} errors ---")
        for e in errors:
            print(f"  FAIL: {e}")
        sys.exit(1)
    print(f"OK: {len(html_files)} HTML files passed all checks ({len(warnings)} warnings).")

if __name__ == "__main__":
    main()
