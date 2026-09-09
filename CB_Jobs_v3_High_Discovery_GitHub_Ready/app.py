import streamlit as st
import pandas as pd

from matcher import score_job, extract_skills
from db import add_job, get_jobs, update_job, delete_job
from resume_utils import extract_resume_text
from sources import fetch_selected_sources

st.set_page_config(page_title="Remote Tech Job Application System", layout="wide")

st.title("Remote Tech Job Application System")
st.caption("Remote-only discovery • Resume matching • Duplicate prevention • Application tracking")

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "discovered_jobs" not in st.session_state:
    st.session_state.discovered_jobs = []

with st.sidebar:
    st.header("Resume")
    resume_file = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
    if resume_file:
        try:
            st.session_state.resume_text = extract_resume_text(resume_file)
            st.success("Resume loaded")
        except Exception as e:
            st.error(str(e))

    st.header("Remote filters")
    country_pref = st.text_input(
        "Remote eligibility keywords",
        value="USA, United States, US, Worldwide, Anywhere, Remote",
        help="Jobs are remote-only. These keywords help prioritize jobs you can work from the U.S."
    )
    apply_threshold = st.slider("Apply Queue threshold", 50, 100, 80)
    review_threshold = st.slider("Review threshold", 40, apply_threshold - 1, 65)

    if st.session_state.resume_text:
        skills = extract_skills(st.session_state.resume_text)
        st.write("Detected skills:")
        st.write(", ".join(skills) if skills else "No default skills detected.")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Find Remote Jobs", "Add / Import", "Tracker", "Dashboard"]
)

def bucket_for(score):
    if score >= apply_threshold:
        return "Apply Queue"
    if score >= review_threshold:
        return "Review"
    return "Skip"

with tab1:
    st.subheader("Find remote tech jobs")
    st.write(
        "Discovery uses public job feeds/APIs. It does not scrape login-protected pages "
        "or bypass CAPTCHA/anti-bot controls."
    )

    sources = st.multiselect(
        "Sources",
        ["Remotive", "Remote OK", "Arbeitnow"],
        default=["Remotive", "Remote OK"],
        help="Arbeitnow is Europe-focused and is optional."
    )

    if st.button("Fetch remote jobs"):
        with st.spinner("Fetching public remote-job feeds..."):
            jobs, errors = fetch_selected_sources(sources)
        st.session_state.discovered_jobs = jobs
        if errors:
            for err in errors:
                st.warning(err)
        st.success(f"Fetched {len(jobs)} remote tech listings before resume scoring.")

    if st.session_state.discovered_jobs:
        if not st.session_state.resume_text:
            st.info("Upload your resume to score and import these jobs.")
        else:
            prefs = [x.strip() for x in country_pref.split(",") if x.strip()]
            scored = []
            for job in st.session_state.discovered_jobs:
                result = score_job(
                    st.session_state.resume_text,
                    job["title"],
                    job["description"],
                    job["location"],
                    prefs
                )
                scored.append({
                    **job,
                    "match_score": result["score"],
                    "bucket": bucket_for(result["score"]),
                    "matched_skills": ", ".join(result["matched_skills"]),
                })

            frame = pd.DataFrame(scored).sort_values("match_score", ascending=False)
            st.dataframe(
                frame[[
                    "source", "company", "title", "location",
                    "match_score", "bucket", "url"
                ]],
                use_container_width=True,
                hide_index=True
            )

            min_score = st.slider("Import jobs scoring at least", 0, 100, review_threshold)
            if st.button("Import qualifying jobs to tracker"):
                added = duplicates = 0
                for job in scored:
                    if job["match_score"] < min_score:
                        continue
                    ok, _ = add_job(
                        job["company"], job["title"], job["url"],
                        job["location"], job["description"],
                        job["match_score"], job["bucket"],
                        source=job["source"], remote_verified=True
                    )
                    if ok:
                        added += 1
                    else:
                        duplicates += 1
                st.success(f"Imported {added}; skipped {duplicates} duplicates.")

with tab2:
    st.subheader("Add one remote job manually")
    with st.form("job_form"):
        c1, c2 = st.columns(2)
        with c1:
            company = st.text_input("Company")
            title = st.text_input("Job title")
            location = st.text_input("Remote location / eligibility", value="Remote")
        with c2:
            url = st.text_input("Application URL")
            source = st.text_input("Source / platform")
        description = st.text_area("Job description", height=220)
        remote_confirmed = st.checkbox("I confirmed this job is remote", value=True)
        submitted = st.form_submit_button("Analyze and Add")

    if submitted:
        if not remote_confirmed:
            st.error("This version is remote-only. Confirm the role is remote before adding it.")
        elif not company or not title:
            st.error("Company and job title are required.")
        elif not st.session_state.resume_text:
            st.error("Upload your resume first.")
        else:
            prefs = [x.strip() for x in country_pref.split(",") if x.strip()]
            result = score_job(
                st.session_state.resume_text, title, description, location, prefs
            )
            bucket = bucket_for(result["score"])
            ok, _ = add_job(
                company, title, url, location, description,
                result["score"], bucket, source=source, remote_verified=True
            )
            if ok:
                st.success(f"Added — Match score: {result['score']}% — {bucket}")
            else:
                st.warning("Duplicate detected. Not added.")

    st.divider()
    st.subheader("Import remote jobs from CSV")
    uploaded_csv = st.file_uploader(
        "CSV columns: company,title,url,location,description",
        type=["csv"]
    )
    source_name = st.text_input("CSV source/platform", value="CSV Import")

    if uploaded_csv and st.session_state.resume_text:
        df = pd.read_csv(uploaded_csv)
        required = {"company", "title", "url", "location", "description"}
        if not required.issubset(set(df.columns)):
            st.error(f"CSV must include: {', '.join(sorted(required))}")
        elif st.button("Analyze and Import Remote CSV"):
            added = duplicates = 0
            prefs = [x.strip() for x in country_pref.split(",") if x.strip()]
            for _, row in df.fillna("").iterrows():
                # Remote-only guard
                remote_text = f"{row['location']} {row['description']}".lower()
                if not any(k in remote_text for k in ["remote", "worldwide", "anywhere"]):
                    continue

                result = score_job(
                    st.session_state.resume_text,
                    row["title"], row["description"], row["location"], prefs
                )
                ok, _ = add_job(
                    row["company"], row["title"], row["url"],
                    row["location"], row["description"],
                    result["score"], bucket_for(result["score"]),
                    source=source_name, remote_verified=True
                )
                if ok:
                    added += 1
                else:
                    duplicates += 1
            st.success(f"Imported {added} remote jobs; skipped {duplicates} duplicates.")

with tab3:
    st.subheader("Remote Application Tracker")
    jobs = get_jobs()

    if jobs.empty:
        st.info("No jobs yet.")
    else:
        jobs = jobs[jobs["remote_verified"] == 1]
        display_cols = [
            "id", "date_found", "source", "company", "title", "location",
            "match_score", "bucket", "status", "date_applied", "url", "notes"
        ]
        st.dataframe(jobs[display_cols], use_container_width=True, hide_index=True)

        csv = jobs.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export tracker CSV",
            data=csv,
            file_name="remote_job_application_tracker.csv",
            mime="text/csv"
        )

        st.divider()
        job_id = st.selectbox("Job ID", jobs["id"].tolist())
        row = jobs[jobs["id"] == job_id].iloc[0]
        st.write(f"**{row['company']} — {row['title']}**")

        statuses = [
            "Not Applied", "Needs Review", "Ready to Apply", "Applied",
            "Interview", "Rejected", "Offer"
        ]
        current = row["status"] if row["status"] in statuses else "Not Applied"
        new_status = st.selectbox("Status", statuses, index=statuses.index(current))
        notes = st.text_area("Notes", value=row["notes"] or "")
        resume_version = st.text_input("Resume version", value=row["resume_version"] or "")
        cover_letter = st.text_area(
            "Cover letter / application notes",
            value=row["cover_letter"] or "", height=160
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save update"):
                update_job(
                    job_id, status=new_status, notes=notes,
                    resume_version=resume_version, cover_letter=cover_letter
                )
                st.success("Updated.")
                st.rerun()
        with c2:
            if st.button("Delete job"):
                delete_job(job_id)
                st.success("Deleted.")
                st.rerun()

with tab4:
    jobs = get_jobs()
    jobs = jobs[jobs["remote_verified"] == 1] if not jobs.empty else jobs
    st.subheader("Remote Job Dashboard")

    if jobs.empty:
        st.info("No remote jobs tracked yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Remote Jobs", len(jobs))
        c2.metric("Apply Queue", int((jobs["bucket"] == "Apply Queue").sum()))
        c3.metric("Applied", int((jobs["status"] == "Applied").sum()))
        c4.metric("Interviews", int((jobs["status"] == "Interview").sum()))

        best = jobs.sort_values("match_score", ascending=False).head(20)
        st.subheader("Best Remote Matches")
        st.dataframe(
            best[[
                "source", "company", "title", "location",
                "match_score", "bucket", "status", "url"
            ]],
            use_container_width=True,
            hide_index=True
        )

st.divider()
st.caption(
    "Remote-only mode is enforced. Applications remain user-approved. "
    "The program does not bypass CAPTCHA, account security, website anti-bot controls, "
    "or invent answers to application questions."
)
