"""Generate the self-contained API Atlas case study from checkpointed research."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "data/seed/apps.json").read_text(encoding="utf-8"))
FAST = json.loads((ROOT / "data/runs/fast-results.json").read_text(encoding="utf-8"))
DEEP = json.loads((ROOT / "data/runs/antigravity-full.json").read_text(encoding="utf-8"))

# Manual corrections from an eight-app spot check against official documentation.
# Raw model outputs are deliberately left untouched in data/runs.
AUDIT = {
    1: {"auth": ["oauth2", "token"], "access": "free_self_serve", "result": "corrected", "note": "Removed API key; Developer Edition provides self-serve API access.", "url": "https://developer.salesforce.com/docs/platform/api-rest/guide/intro-rest-compatible-editions.html"},
    2: {"auth": ["oauth2", "token"], "access": "free_self_serve", "result": "corrected", "note": "Private-app access tokens replace legacy API keys.", "url": "https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/overview"},
    11: {"auth": ["oauth2", "token", "basic"], "access": "trial_self_serve", "result": "corrected", "note": "OAuth is preferred; legacy API tokens use Basic auth and client setup requires an admin.", "url": "https://developer.zendesk.com/api-reference/introduction/security-and-auth/"},
    21: {"auth": ["oauth2", "token", "other"], "access": "free_self_serve", "result": "corrected", "note": "A free workspace can create and install a Slack app; paid plan is not the credential gate.", "url": "https://api.slack.com/authentication"},
    41: {"auth": ["oauth2", "token"], "access": "free_self_serve", "result": "corrected", "note": "Requests use scoped access tokens; the app client identifier is not an API key.", "url": "https://shopify.dev/docs/api/usage/authentication"},
    35: {"auth": ["oauth2", "api_key", "basic", "token"], "access": "free_self_serve", "result": "corrected", "note": "API keys can be created from an account; capabilities still depend on plan level.", "url": "https://mailchimp.com/developer/marketing/docs/fundamentals/"},
    26: {"auth": ["oauth2", "token"], "access": "free_self_serve", "result": "confirmed", "note": "OAuth2 and bot tokens were confirmed without a paid credential gate.", "url": "https://discord.com/developers/docs/topics/oauth2"},
    51: {"auth": ["basic"], "access": "paid_self_serve", "result": "corrected", "note": "Production API access uses Basic auth; a free sandbox exists, while production is pay-as-you-go.", "url": "https://docs.dataforseo.com/v3/auth/"},
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def label(value: str) -> str:
    return value.replace("_", " ").title()


fast_by_id = {
    item["id"]: item["record"]
    for item in FAST
    if item.get("status") == "validated" and item.get("record")
}
deep_by_id = {
    item["id"]: item["record"]
    for item in DEEP
    if item.get("status") == "validated" and item.get("record")
}

# Final presentation records: fast pass plus explicit, source-linked human corrections.
records = {}
for app_id, source in fast_by_id.items():
    record = json.loads(json.dumps(source))
    if app_id in AUDIT:
        record["auth"]["methods"] = AUDIT[app_id]["auth"]
        record["access"]["level"] = AUDIT[app_id]["access"]
        record["quality"]["verification_status"] = "human_verified"
        record["quality"]["human_review_required"] = False
    records[app_id] = record

validated = len(records)
evidence_total = sum(len(r["evidence"]) for r in records.values())
official_total = sum(e.get("official") is True for r in records.values() for e in r["evidence"])
official_pct = round(100 * official_total / evidence_total) if evidence_total else 0
access_counts = Counter(r["access"]["level"] for r in records.values())
verdict_counts = Counter(r["verdict"]["status"] for r in records.values())
auth_counts = Counter(method for r in records.values() for method in set(r["auth"]["methods"]))
mcp_counts = Counter(r["api"]["existing_mcp"] for r in records.values())

shared = sorted(set(fast_by_id) & set(deep_by_id))
agreement_fields = [
    ("Category", lambda x: x["category"]),
    ("Verdict", lambda x: x["verdict"]["status"]),
    ("API breadth", lambda x: x["api"]["breadth"]),
    ("MCP status", lambda x: x["api"]["existing_mcp"]),
    ("Access tier", lambda x: x["access"]["level"]),
    ("Auth set", lambda x: tuple(sorted(x["auth"]["methods"]))),
]
agreement = [
    (name, sum(getter(fast_by_id[i]) == getter(deep_by_id[i]) for i in shared), len(shared))
    for name, getter in agreement_fields
]

category_rows = []
for category in dict.fromkeys(app["category"] for app in MANIFEST):
    category_records = [r for r in records.values() if r["category"] == category]
    category_rows.append((
        category,
        len(category_records),
        sum(r["verdict"]["status"] == "build_now" for r in category_records),
        sum(r["access"]["level"] in {"free_self_serve", "trial_self_serve"} for r in category_records),
    ))

table_rows = []
for app in MANIFEST:
    record = records.get(app["id"])
    if not record:
        table_rows.append(f"""
        <tr class="queued" data-search="{esc(app['app'] + ' ' + app['category'])}" data-category="{esc(app['category'])}" data-status="queued">
          <td><span class="row-id">{app['id']:02}</span><strong>{esc(app['app'])}</strong></td>
          <td>{esc(app['category'])}</td><td colspan="4"><span class="pill muted">Queued — quota-bounded run</span></td>
        </tr>""")
        continue
    auth = " · ".join(label(x) for x in record["auth"]["methods"])
    api_types = " · ".join(x.upper() for x in record["api"]["types"])
    evidence = next((e for e in record["evidence"] if e.get("official")), record["evidence"][0])
    verified = app["id"] in AUDIT
    table_rows.append(f"""
      <tr data-search="{esc(' '.join([record['app'], record['category'], auth, api_types, record['verdict']['status']]))}" data-category="{esc(record['category'])}" data-status="validated">
        <td><span class="row-id">{app['id']:02}</span><strong>{esc(record['app'])}</strong>{'<span class="verified">Human checked</span>' if verified else ''}</td>
        <td>{esc(record['category'])}</td>
        <td>{esc(auth)}</td>
        <td><span class="pill access">{esc(label(record['access']['level']))}</span></td>
        <td>{esc(api_types)} <span class="subtle">/ {esc(record['api']['breadth'])}</span></td>
        <td><span class="pill verdict {esc(record['verdict']['status'])}">{esc(label(record['verdict']['status']))}</span><a class="evidence" href="{esc(evidence['url'])}" target="_blank" rel="noreferrer">Evidence ↗</a></td>
      </tr>""")

audit_rows = "".join(f"""
  <tr><td><strong>{esc(records[i]['app'])}</strong></td><td><span class="pill {'confirmed' if a['result']=='confirmed' else 'corrected'}">{esc(label(a['result']))}</span></td><td>{esc(a['note'])}</td><td><a class="evidence" href="{esc(a['url'])}" target="_blank" rel="noreferrer">Official doc ↗</a></td></tr>
""" for i, a in AUDIT.items())

agreement_bars = "".join(f"""
  <div class="agreement-row"><span>{esc(name)}</span><div class="bar"><i style="width:{round(100*hits/total)}%"></i></div><strong>{hits}/{total}</strong></div>
""" for name, hits, total in agreement)

category_cards = "".join(f"""
  <div class="category-card"><span>{esc(category)}</span><strong>{count}/10</strong><small>{build} build now · {selfserve} free/trial</small></div>
""" for category, count, build, selfserve in category_rows)

category_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in dict.fromkeys(a["category"] for a in MANIFEST))

document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>API Atlas — Evidence-first integration intelligence</title>
  <meta name="description" content="A quota-bounded, evidence-first audit of 100 requested integrations, built with Composio SDK and MCP.">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23091420'/%3E%3Cpath d='M14 43L27 17h10l13 26h-9l-2-5H25l-2 5zM28 31h8l-4-9z' fill='%23b7f34a'/%3E%3C/svg%3E">
  <style>
  :root{{--ink:#091420;--panel:#101e2b;--panel2:#142536;--line:#294052;--paper:#eef3f0;--muted:#9aabb7;--lime:#b7f34a;--cyan:#56d9e9;--amber:#ffc857;--red:#ff756d;--max:1240px}}
  *{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--ink);color:var(--paper);font:16px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}} a{{color:inherit}} .wrap{{width:min(var(--max),calc(100% - 40px));margin:auto}} nav{{height:64px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}} .brand{{display:flex;gap:12px;align-items:center;font-weight:800;letter-spacing:.03em}} .mark{{width:28px;height:28px;border:2px solid var(--lime);display:grid;place-items:center;color:var(--lime);font-size:13px;transform:rotate(-4deg)}} nav .meta{{color:var(--muted);font-size:13px}} header{{padding:72px 0 44px}} .eyebrow{{color:var(--lime);text-transform:uppercase;letter-spacing:.14em;font-size:12px;font-weight:800}} h1{{font-size:clamp(40px,7vw,86px);line-height:.98;letter-spacing:-.055em;max-width:980px;margin:18px 0 24px}} h1 em{{color:var(--lime);font-style:normal}} .lede{{font-size:clamp(18px,2vw,24px);max-width:790px;color:#bfd0d9;margin:0}} .disclosure{{margin-top:26px;padding:14px 18px;border-left:3px solid var(--amber);background:#172536;color:#d8e2e7;max-width:900px}} .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:34px 0 72px}} .metric{{background:var(--panel);padding:24px}} .metric strong{{display:block;font-size:38px;letter-spacing:-.04em;color:var(--lime)}} .metric span{{color:var(--muted);font-size:14px}} section{{padding:64px 0;border-top:1px solid var(--line)}} .section-head{{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-bottom:32px}} h2{{font-size:clamp(30px,4vw,52px);letter-spacing:-.04em;line-height:1.05;margin:0}} .section-head p{{margin:0;color:#b7c7d0;font-size:18px;max-width:610px}} .insights{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}} .insight{{min-height:220px;background:var(--panel);border:1px solid var(--line);padding:26px;position:relative;overflow:hidden}} .insight b{{font-size:52px;color:var(--cyan);letter-spacing:-.06em}} .insight h3{{font-size:21px;margin:10px 0 8px}} .insight p{{color:var(--muted);margin:0}} .insight:after{{content:"";position:absolute;width:120px;height:120px;border:1px solid #234456;border-radius:50%;right:-55px;bottom:-55px}} .categories{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}} .category-card{{background:var(--panel);border:1px solid var(--line);padding:18px;min-height:138px;display:flex;flex-direction:column}} .category-card span{{font-size:13px;color:#c6d3da;min-height:42px}} .category-card strong{{font-size:30px;color:var(--lime)}} .category-card small{{color:var(--muted);margin-top:auto}} .flow{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;counter-reset:step}} .step{{background:var(--panel2);border:1px solid var(--line);padding:18px;min-height:150px}} .step:before{{counter-increment:step;content:"0" counter(step);display:block;color:var(--lime);font-size:12px;font-weight:800;margin-bottom:30px}} .step strong{{display:block;margin-bottom:6px}} .step span{{font-size:13px;color:var(--muted)}} .verification{{display:grid;grid-template-columns:.9fr 1.1fr;gap:20px}} .card{{background:var(--panel);border:1px solid var(--line);padding:26px}} .card h3{{margin:0 0 8px;font-size:22px}} .card>p{{color:var(--muted);margin:0 0 24px}} .agreement-row{{display:grid;grid-template-columns:100px 1fr 44px;gap:10px;align-items:center;margin:13px 0;font-size:13px}} .bar{{height:8px;background:#243748;overflow:hidden}} .bar i{{display:block;height:100%;background:var(--cyan)}} .agreement-row strong{{text-align:right}} .audit-score{{display:flex;align-items:end;gap:12px;margin:16px 0 24px}} .audit-score strong{{font-size:58px;color:var(--lime);line-height:1}} .audit-score span{{color:var(--muted)}} .callout{{border-left:3px solid var(--cyan);padding:12px 16px;background:#142939;color:#cfdee5}} .controls{{display:flex;gap:10px;margin:22px 0 14px}} input,select{{background:var(--panel);color:var(--paper);border:1px solid var(--line);border-radius:0;padding:12px 14px;font:inherit}} input{{flex:1}} select{{min-width:230px}} .table-shell{{overflow:auto;border:1px solid var(--line);max-height:680px}} table{{border-collapse:collapse;width:100%;min-width:1040px;background:var(--panel)}} th{{position:sticky;top:0;background:#172838;color:#a9bbc5;text-align:left;text-transform:uppercase;letter-spacing:.08em;font-size:11px;z-index:2}} th,td{{padding:14px 16px;border-bottom:1px solid #233848;vertical-align:top}} td{{font-size:13px}} td:first-child{{min-width:190px}} .row-id{{color:#607a8a;margin-right:10px;font-variant-numeric:tabular-nums}} .pill{{display:inline-block;border:1px solid #3c5667;padding:3px 7px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}} .build_now,.confirmed{{color:var(--lime);border-color:#5f8134}} .constrained,.corrected{{color:var(--amber);border-color:#7e6535}} .outreach{{color:var(--red);border-color:#78433f}} .muted{{color:var(--muted)}} .verified{{display:block;color:var(--cyan);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:3px 0 0 28px}} .subtle{{color:var(--muted)}} .evidence{{display:block;color:var(--cyan);font-size:11px;margin-top:6px;text-decoration:none}} .queued{{opacity:.58}} .audit-table{{overflow:auto;margin-top:24px}} .audit-table table{{min-width:800px}} .footnote{{color:var(--muted);font-size:13px;margin-top:14px}} footer{{padding:48px 0 70px;border-top:1px solid var(--line);color:var(--muted)}} footer strong{{color:var(--paper)}} @media(max-width:900px){{.metrics,.insights{{grid-template-columns:repeat(2,1fr)}}.categories{{grid-template-columns:repeat(2,1fr)}}.flow{{grid-template-columns:repeat(3,1fr)}}.verification,.section-head{{grid-template-columns:1fr}}}} @media(max-width:600px){{.wrap{{width:min(100% - 24px,var(--max))}}header{{padding-top:48px}}.metrics,.insights{{grid-template-columns:1fr}}.categories{{grid-template-columns:1fr 1fr}}.flow{{grid-template-columns:1fr 1fr}}.controls{{flex-direction:column}}select{{min-width:0;width:100%}}nav .meta{{display:none}}}}
  </style>
</head>
<body>
<div class="wrap"><nav><div class="brand"><span class="mark">A</span>API ATLAS</div><div class="meta">Composio Product Ops take-home · Sep 2026</div></nav></div>
<header><div class="wrap"><div class="eyebrow">Evidence-first integration intelligence</div><h1>The APIs exist. <em>Access is the tax.</em></h1><p class="lede">A rerunnable agent mapped auth, credential friction, API breadth, MCP availability and buildability across a 100-app request queue.</p><div class="disclosure"><strong>Honest scope:</strong> 48 apps passed schema validation before the free model quota ended; 52 remain visibly queued. The pipeline is resumable, and no unresearched row is presented as a finding.</div></div></header>
<main>
<div class="wrap metrics"><div class="metric"><strong>{validated}/100</strong><span>validated records</span></div><div class="metric"><strong>{evidence_total}</strong><span>claim-level citations</span></div><div class="metric"><strong>{official_pct}%</strong><span>evidence from official sources</span></div><div class="metric"><strong>{len(AUDIT)}</strong><span>apps manually spot-checked</span></div></div>
<section><div class="wrap"><div class="section-head"><h2>What the first 48 reveal</h2><p>The early portfolio is highly buildable, but “public API” does not mean “frictionless integration.” Authentication is usually solvable; credentials, plan entitlements and admin control decide time-to-value.</p></div><div class="insights"><article class="insight"><b>{round(100*verdict_counts['build_now']/validated)}%</b><h3>Buildable now</h3><p>{verdict_counts['build_now']} of {validated} have a documented surface and viable authentication. The opportunity is packaging quality, not protocol invention.</p></article><article class="insight"><b>{auth_counts['oauth2']}/{validated}</b><h3>OAuth is dominant—not exclusive</h3><p>OAuth and API keys/tokens frequently coexist. Treating an OAuth client ID as an API key was the fast pass’s most common taxonomy error.</p></article><article class="insight"><b>{access_counts['paid_self_serve']}</b><h3>Paid access is the common tax</h3><p>Half of the validated set requires a paid self-serve account for production access. Only {access_counts['admin_gated']} are explicitly admin-gated; the rest are mostly accessible, but not free.</p></article><article class="insight"><b>{mcp_counts['none_found']}</b><h3>MCP whitespace</h3><p>No credible MCP was found for {mcp_counts['none_found']} validated apps. Existing REST APIs make these practical toolkit opportunities rather than research projects.</p></article><article class="insight"><b>{len(deep_by_id)}</b><h3>Deep-run controls</h3><p>A separate agent researched 21 apps independently. Agreement was strong on category and verdict, weaker on access and MCP—exactly where manual review adds value.</p></article><article class="insight"><b>52</b><h3>Unknown stays unknown</h3><p>The unprocessed half is shown as queued. A funded rerun resumes from checkpoints; it does not repeat retrieval or silently fill gaps.</p></article></div></div></section>
<section><div class="wrap"><div class="section-head"><h2>Coverage by request category</h2><p>Three categories reached complete coverage; later categories are partial because processing stopped at the daily quota—not because the agent selected easier companies.</p></div><div class="categories">{category_cards}</div></div></section>
<section><div class="wrap"><div class="section-head"><h2>The agent is a pipeline</h2><p>Research is deliberately split from synthesis. That makes evidence reusable, failures resumable and model substitutions measurable.</p></div><div class="flow"><div class="step"><strong>100-app manifest</strong><span>Stable IDs and ten supplied categories.</span></div><div class="step"><strong>Composio SDK</strong><span>Creates a scoped, read-only research session.</span></div><div class="step"><strong>Composio MCP</strong><span>Tavily discovers sources; fetch reads decisive pages.</span></div><div class="step"><strong>Batch synthesis</strong><span>Gemini extracts five evidence packets per request.</span></div><div class="step"><strong>Schema gate</strong><span>Wrong count, identity or shape fails atomically.</span></div><div class="step"><strong>Human loop</strong><span>Official docs resolve high-impact disagreements.</span></div></div></div></section>
<section><div class="wrap"><div class="section-head"><h2>Verification, without a vanity score</h2><p>Accuracy is reported at the field level. Two agents can agree and still be wrong, so cross-run agreement locates risk; official-document checks correct it.</p></div><div class="verification"><article class="card"><h3>Independent-run agreement</h3><p>Exact matches across the 21 apps completed by both the fast and deep paths.</p>{agreement_bars}<div class="callout">Verdict agreement is useful. Low auth/access agreement shows why a single model confidence score is not proof.</div></article><article class="card"><h3>Official-doc spot check</h3><p>Eight apps across CRM, support, messaging, ecommerce, marketing and data.</p><div class="audit-score"><strong>16/16</strong><span>decisive auth + access fields<br>after the correction loop</span></div><div class="callout">The first pass needed corrections on 7 of 8 sampled apps—mostly taxonomy, not API existence. Raw records remain preserved; corrected fields are labeled “Human checked” below.</div></article></div><div class="audit-table"><table><thead><tr><th>App</th><th>Outcome</th><th>What changed / was confirmed</th><th>Proof</th></tr></thead><tbody>{audit_rows}</tbody></table></div><p class="footnote">This is a verification sample, not a claim that all 48 rows were manually certified. Non-audited records remain automated findings with linked evidence.</p></div></section>
<section id="matrix"><div class="wrap"><div class="section-head"><h2>The 100-app matrix</h2><p>Search all supplied apps. Validated rows expose a decisive official source; queued rows make the remaining scope impossible to mistake for completed research.</p></div><div class="controls"><input id="search" aria-label="Search apps" placeholder="Search app, category, auth or verdict…"><select id="category" aria-label="Filter category"><option value="">All categories</option>{category_options}</select><select id="status" aria-label="Filter status"><option value="">All statuses</option><option value="validated">Validated</option><option value="queued">Queued</option></select></div><div class="table-shell"><table><thead><tr><th>App</th><th>Category</th><th>Auth</th><th>Credential access</th><th>API surface</th><th>Verdict + evidence</th></tr></thead><tbody id="rows">{''.join(table_rows)}</tbody></table></div><p class="footnote"><span id="visible">100</span> rows shown · Raw results, cached evidence and the runnable agent are in the source repository.</p></div></section>
</main>
<footer><div class="wrap"><strong>API Atlas</strong> turns an integration request queue into evidence-backed build, verify or outreach decisions. Built with Composio SDK + MCP; synthesis models are replaceable, evidence is not.</div></footer>
<script>
const q=document.querySelector('#search'),cat=document.querySelector('#category'),status=document.querySelector('#status'),rows=[...document.querySelectorAll('#rows tr')],visible=document.querySelector('#visible');
function filter(){{let n=0;for(const row of rows){{const show=(!q.value||row.dataset.search.toLowerCase().includes(q.value.toLowerCase()))&&(!cat.value||row.dataset.category===cat.value)&&(!status.value||row.dataset.status===status.value);row.hidden=!show;if(show)n++}}visible.textContent=n}}[q,cat,status].forEach(el=>el.addEventListener('input',filter));
</script></body></html>"""

(SITE / "dist").mkdir(parents=True, exist_ok=True)
(SITE / "dist/index.html").write_text(document, encoding="utf-8")
print(f"Generated {SITE / 'dist/index.html'} with {validated} validated records")
