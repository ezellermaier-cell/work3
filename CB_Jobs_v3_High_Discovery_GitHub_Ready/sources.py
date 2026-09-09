import html, re, requests, xml.etree.ElementTree as ET
from urllib.parse import urlencode

HEADERS = {"User-Agent": "CBJobs/3.0 (personal remote job search client)"}

SEARCH_QUERIES = [
    "it support",
    "technical support",
    "help desk",
    "service desk",
    "desktop support",
    "systems administrator",
    "system administrator",
    "sysadmin",
    "it administrator",
    "it specialist",
    "support engineer",
    "technical support engineer",
    "application support",
    "infrastructure",
    "network administrator",
    "network engineer",
    "network support",
    "cloud support",
    "cloud administrator",
    "cybersecurity",
    "security analyst",
    "security operations",
    "soc analyst",
    "incident response",
    "active directory",
    "microsoft 365",
    "intune",
    "endpoint",
    "identity access",
]

BROAD_TECH_HINTS = [
    "support","systems","system","administrator","admin","security","cyber",
    "network","infrastructure","cloud","endpoint","identity","technical",
    "help desk","service desk","desktop","soc","it ","information technology",
    "microsoft 365","active directory","intune","azure","windows","linux",
    "engineer","analyst","operations","application support"
]

def _clean(v):
    v = html.unescape(v or "")
    v = re.sub(r"<script.*?</script>", " ", v, flags=re.I|re.S)
    v = re.sub(r"<style.*?</style>", " ", v, flags=re.I|re.S)
    v = re.sub(r"<[^>]+>", " ", v)
    return re.sub(r"\s+", " ", v).strip()

def _likely_tech(title, desc="", tags=""):
    hay = f"{title} {tags} {desc[:2500]}".lower()
    return any(t in hay for t in BROAD_TECH_HINTS)

def _dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        url=(j.get("url") or "").split("?")[0].strip().lower()
        key=(j.get("company","").strip().lower(), j.get("title","").strip().lower(), url)
        if key in seen: continue
        seen.add(key); out.append(j)
    return out

def fetch_remotive(limit=500):
    r=requests.get("https://remotive.com/api/remote-jobs",headers=HEADERS,timeout=35)
    r.raise_for_status()
    out=[]
    for i in r.json().get("jobs",[]):
        title=i.get("title",""); desc=_clean(i.get("description",""))
        if not _likely_tech(title,desc,i.get("category","")): continue
        out.append({
            "company":i.get("company_name",""),"title":title,"url":i.get("url",""),
            "location":i.get("candidate_required_location","Remote") or "Remote",
            "description":desc,"source":"Remotive","remote_verified":True
        })
        if len(out)>=limit: break
    return out

def fetch_remoteok(limit=600):
    r=requests.get("https://remoteok.com/api",headers=HEADERS,timeout=35)
    r.raise_for_status()
    out=[]
    for i in r.json():
        if not isinstance(i,dict) or not i.get("position"): continue
        title=i.get("position",""); desc=_clean(i.get("description",""))
        tags=" ".join(i.get("tags",[]) or [])
        if not _likely_tech(title,desc,tags): continue
        out.append({
            "company":i.get("company",""),"title":title,"url":i.get("url",""),
            "location":i.get("location","Remote") or "Remote",
            "description":f"{desc} {tags}".strip(),"source":"Remote OK","remote_verified":True
        })
        if len(out)>=limit: break
    return out

def fetch_jobicy(limit_per_query=200):
    out=[]
    for q in SEARCH_QUERIES:
        try:
            r=requests.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count":limit_per_query,"tag":q},
                headers=HEADERS,timeout=30
            )
            r.raise_for_status()
            data=r.json()
            for i in data.get("jobs",[]):
                title=i.get("jobTitle","")
                desc=_clean(i.get("jobDescription",""))
                industries=" ".join(i.get("jobIndustry",[]) or [])
                if not _likely_tech(title,desc,industries): continue
                out.append({
                    "company":i.get("companyName",""),"title":title,"url":i.get("url",""),
                    "location":i.get("jobGeo","Remote") or "Remote",
                    "description":desc,"source":"Jobicy","remote_verified":True
                })
        except Exception:
            continue
    return _dedupe(out)

def fetch_himalayas(max_pages_per_query=4):
    out=[]
    for q in SEARCH_QUERIES:
        for page in range(1,max_pages_per_query+1):
            try:
                r=requests.get(
                    "https://himalayas.app/jobs/api/search",
                    params={"q":q,"sort":"recent","page":page},
                    headers=HEADERS,timeout=30
                )
                r.raise_for_status()
                data=r.json()
                jobs=data.get("jobs",[]) if isinstance(data,dict) else []
                if not jobs: break
                for i in jobs:
                    title=i.get("title","")
                    desc=_clean(i.get("description") or i.get("excerpt") or "")
                    cats=" ".join((i.get("categories") or []) + (i.get("parentCategories") or []))
                    if not _likely_tech(title,desc,cats): continue
                    locs=i.get("locationRestrictions") or []
                    out.append({
                        "company":i.get("companyName",""),"title":title,
                        "url":i.get("applicationLink",""),
                        "location":", ".join(locs) if locs else "Worldwide / Remote",
                        "description":desc,"source":"Himalayas","remote_verified":True
                    })
            except Exception:
                break
    return _dedupe(out)

def fetch_arbeitnow(max_pages=8):
    out=[]
    url="https://www.arbeitnow.com/api/job-board-api"
    for page in range(1,max_pages+1):
        try:
            r=requests.get(url,params={"page":page},headers=HEADERS,timeout=30)
            r.raise_for_status()
            data=r.json()
            batch=data.get("data",[])
            if not batch: break
            for i in batch:
                if not i.get("remote",False): continue
                title=i.get("title",""); desc=_clean(i.get("description",""))
                tags=" ".join(i.get("tags",[]) or [])
                if not _likely_tech(title,desc,tags): continue
                out.append({
                    "company":i.get("company_name",""),"title":title,"url":i.get("url",""),
                    "location":i.get("location","Remote") or "Remote",
                    "description":f"{desc} {tags}".strip(),"source":"Arbeitnow","remote_verified":True
                })
        except Exception:
            break
    return _dedupe(out)

def fetch_weworkremotely(limit=500):
    feeds=[
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
    ]
    out=[]
    for feed in feeds:
        try:
            r=requests.get(feed,headers=HEADERS,timeout=30)
            r.raise_for_status()
            root=ET.fromstring(r.content)
            for item in root.findall(".//item"):
                raw=item.findtext("title") or ""
                link=item.findtext("link") or ""
                desc=_clean(item.findtext("description") or "")
                company=""; title=raw
                if ":" in raw:
                    company,title=[x.strip() for x in raw.split(":",1)]
                if not _likely_tech(title,desc): continue
                out.append({
                    "company":company,"title":title,"url":link,"location":"Remote",
                    "description":desc,"source":"We Work Remotely","remote_verified":True
                })
                if len(out)>=limit: return _dedupe(out)
        except Exception:
            continue
    return _dedupe(out)

SOURCE_MAP={
    "Remotive":fetch_remotive,
    "Remote OK":fetch_remoteok,
    "Jobicy":fetch_jobicy,
    "Himalayas":fetch_himalayas,
    "Arbeitnow":fetch_arbeitnow,
    "We Work Remotely":fetch_weworkremotely,
}

def fetch_selected_sources(selected=None):
    selected=selected or list(SOURCE_MAP.keys())
    jobs=[]; errors=[]; counts={}
    for name in selected:
        fn=SOURCE_MAP.get(name)
        if not fn: continue
        try:
            batch=fn()
            counts[name]=len(batch)
            jobs.extend(batch)
        except Exception as e:
            counts[name]=0
            errors.append(f"{name}: {e}")
    return _dedupe(jobs), errors
