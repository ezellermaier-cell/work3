from pathlib import Path
import re
from playwright.sync_api import sync_playwright

SENSITIVE_TERMS = [
    "sponsorship", "visa", "work authorization", "authorized to work",
    "salary", "compensation", "desired pay", "expected pay",
    "gender", "race", "ethnicity", "veteran", "disability",
    "citizenship", "social security", "ssn",
    "criminal", "conviction", "background check"
]

CAPTCHA_TERMS = [
    "captcha", "recaptcha", "hcaptcha", "verify you are human"
]

def _label_text(el):
    try:
        aria = el.get_attribute("aria-label") or ""
        name = el.get_attribute("name") or ""
        placeholder = el.get_attribute("placeholder") or ""
        eid = el.get_attribute("id") or ""
        return " ".join([aria, name, placeholder, eid]).lower()
    except Exception:
        return ""

def _fill_by_keywords(page, keywords, value):
    if not value:
        return False
    selectors = ["input", "textarea"]
    for sel in selectors:
        for el in page.locator(sel).all():
            text = _label_text(el)
            if any(k in text for k in keywords):
                try:
                    if el.is_visible() and el.is_enabled():
                        el.fill(value)
                        return True
                except Exception:
                    pass
    return False

def inspect_page_for_blockers(page):
    text = (page.locator("body").inner_text(timeout=10000) or "").lower()
    blockers = []
    if any(t in text for t in CAPTCHA_TERMS):
        blockers.append("CAPTCHA / human verification")
    for term in SENSITIVE_TERMS:
        if term in text:
            blockers.append(f"Sensitive question: {term}")
    # login/auth walls
    if any(t in text for t in ["sign in", "log in", "login required", "create account"]):
        blockers.append("Login/account step")
    return sorted(set(blockers))

def apply_to_job(url, profile, resume_path, auto_submit=False, headless=False):
    """
    Best-effort helper for straightforward forms.
    Never bypasses CAPTCHA or login walls and refuses to auto-submit
    when sensitive/ambiguous questions are detected.
    """
    result = {
        "url": url,
        "status": "Needs Review",
        "filled": [],
        "blockers": [],
        "submitted": False,
        "message": ""
    }

    with sync_playwright() as p:
        browser = None
        launch_errors = []
        for channel in ("msedge", "chrome"):
            try:
                browser = p.chromium.launch(channel=channel, headless=headless)
                break
            except Exception as e:
                launch_errors.append(f"{channel}: {e}")
        if browser is None:
            raise RuntimeError(
                "CB Jobs could not open Microsoft Edge or Google Chrome. "
                "Install one of those browsers. " + " | ".join(launch_errors)
            )

        context = browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)

        blockers = inspect_page_for_blockers(page)
        result["blockers"] = blockers

        mapping = [
            (["first name", "firstname", "first_name"], profile.get("first_name"), "First name"),
            (["last name", "lastname", "last_name"], profile.get("last_name"), "Last name"),
            (["full name", "fullname", "name"], profile.get("full_name"), "Full name"),
            (["email", "e-mail"], profile.get("email"), "Email"),
            (["phone", "mobile", "telephone"], profile.get("phone"), "Phone"),
            (["city", "location"], profile.get("location"), "Location"),
            (["linkedin"], profile.get("linkedin"), "LinkedIn"),
            (["portfolio", "website", "personal site"], profile.get("portfolio"), "Portfolio"),
        ]

        for keys, value, label in mapping:
            if _fill_by_keywords(page, keys, value):
                result["filled"].append(label)

        # resume upload
        if resume_path and Path(resume_path).exists():
            for inp in page.locator('input[type="file"]').all():
                try:
                    if inp.is_enabled():
                        inp.set_input_files(str(resume_path))
                        result["filled"].append("Resume")
                        break
                except Exception:
                    pass

        # Always stop before submit if anything sensitive/protected appears.
        if blockers:
            result["status"] = "Needs Approval"
            result["message"] = "Form was partially filled, but CB Jobs stopped before submission."
            if not headless:
                page.wait_for_timeout(120000)  # give user up to 2 min to inspect
            browser.close()
            return result

        if auto_submit:
            # Submit only on clearly labelled submit/apply buttons.
            candidates = page.get_by_role("button").all()
            clicked = False
            for btn in candidates:
                try:
                    txt = (btn.inner_text() or "").strip().lower()
                    if txt in {"submit application", "submit", "apply", "apply now"}:
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            page.wait_for_timeout(3000)
                            clicked = True
                            break
                except Exception:
                    pass

            if clicked:
                result["status"] = "Submitted"
                result["submitted"] = True
                result["message"] = "Application submitted on a straightforward form."
            else:
                result["status"] = "Needs Review"
                result["message"] = "Fields were filled but no unambiguous submit button was found."
        else:
            result["status"] = "Ready for Review"
            result["message"] = "Fields were filled. Review the browser and submit manually."

        if not headless:
            page.wait_for_timeout(120000)
        browser.close()
        return result
