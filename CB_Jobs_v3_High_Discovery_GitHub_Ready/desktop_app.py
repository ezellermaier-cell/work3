import sys, json, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from PIL import Image

from resume_utils import extract_resume_text
from runner import run_job_search
from db import get_jobs
from scheduler import install_daily_task, remove_daily_task, task_exists
from auto_apply import apply_to_job

APP_DIR = Path.home() / "CB Jobs"
APP_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DIR / "settings.json"
RESUME_CACHE = APP_DIR / "resume.txt"

BG = "#06090F"
PANEL = "#0B111B"
PANEL2 = "#101827"
CYAN = "#20E3FF"
CYAN2 = "#0AA6C7"
GREEN = "#5CFFB0"
TEXT = "#E8F8FF"
MUTED = "#7F9AA8"
DANGER = "#FF5B7F"

def resource_path(name):
    if getattr(sys,"frozen",False):
        return Path(getattr(sys,"_MEIPASS",".")) / name
    return Path(__file__).resolve().parent / name

ctk.set_appearance_mode("dark")

class LocalUpload:
    def __init__(self,path):
        self.path=Path(path); self.name=self.path.name
    def getvalue(self): return self.path.read_bytes()

class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("CB Jobs")
        self.geometry("1280x820")
        self.minsize(1080,700)
        try: self.iconbitmap(str(resource_path("cb_jobs.ico")))
        except Exception: pass

        self.resume_text=""
        self.resume_path=""
        self.last_run=tk.StringVar(value="Never")
        self.status=tk.StringVar(value="SYSTEM READY")
        self.schedule=tk.StringVar(value="ARMED" if task_exists() else "OFFLINE")
        self.auto_apply=tk.BooleanVar(value=False)
        self.profile={k:tk.StringVar() for k in
            ["first_name","last_name","email","phone","location","linkedin","portfolio"]}

        self.load_settings()
        self.build()
        self.refresh_jobs()

    def card(self,parent,title,value,row,col):
        f=ctk.CTkFrame(parent,fg_color=PANEL2,corner_radius=14,border_width=1,border_color=CYAN2)
        f.grid(row=row,column=col,sticky="nsew",padx=7,pady=7)
        ctk.CTkLabel(f,text=title.upper(),text_color=MUTED,font=ctk.CTkFont(size=11,weight="bold")).pack(anchor="w",padx=16,pady=(13,2))
        lab=ctk.CTkLabel(f,text=value,text_color=TEXT,font=ctk.CTkFont(size=20,weight="bold"))
        lab.pack(anchor="w",padx=16,pady=(0,14))
        return lab

    def neon_button(self,parent,text,command,accent=CYAN):
        return ctk.CTkButton(
            parent,text=text,command=command,height=42,corner_radius=10,
            fg_color=accent,hover_color=CYAN2,text_color="#001014",
            font=ctk.CTkFont(size=13,weight="bold")
        )

    def load_settings(self):
        if RESUME_CACHE.exists():
            self.resume_text=RESUME_CACHE.read_text(encoding="utf-8",errors="ignore")
        if SETTINGS_FILE.exists():
            try:
                d=json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self.resume_path=d.get("resume_path","")
                self.last_run.set(d.get("last_run","Never"))
                self.auto_apply.set(bool(d.get("auto_apply",False)))
                for k,v in self.profile.items(): v.set(d.get("profile",{}).get(k,""))
            except Exception: pass

    def save_settings(self):
        SETTINGS_FILE.write_text(json.dumps({
            "resume_path":self.resume_path,
            "last_run":self.last_run.get(),
            "auto_apply":bool(self.auto_apply.get()),
            "profile":{k:v.get() for k,v in self.profile.items()}
        },indent=2),encoding="utf-8")

    def build(self):
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(0,weight=1)

        side=ctk.CTkFrame(self,width=290,corner_radius=0,fg_color="#07101A")
        side.grid(row=0,column=0,sticky="nsw")
        side.grid_propagate(False)

        try:
            logo=ctk.CTkImage(Image.open(resource_path("cb_jobs.png")),size=(132,132))
            ctk.CTkLabel(side,image=logo,text="").pack(pady=(24,6))
            self.logo_ref=logo
        except Exception: pass

        ctk.CTkLabel(side,text="CB JOBS",text_color=CYAN,
                     font=ctk.CTkFont(size=30,weight="bold")).pack()
        ctk.CTkLabel(side,text="CYBER CAREER AUTOMATION",
                     text_color=MUTED,font=ctk.CTkFont(size=11,weight="bold")).pack(pady=(0,22))

        self.neon_button(side,"UPLOAD RESUME",self.upload_resume).pack(fill="x",padx=24,pady=5)
        self.neon_button(side,"RUN NOW",self.run_now,GREEN).pack(fill="x",padx=24,pady=(12,5))

        ctk.CTkSwitch(side,text="AUTO APPLY SAFE FORMS",
                      variable=self.auto_apply,command=self.save_settings,
                      button_color=CYAN,progress_color=CYAN2,text_color=TEXT).pack(anchor="w",padx=24,pady=(18,4))
        ctk.CTkLabel(side,text="Stops on CAPTCHA, logins, salary, sponsorship,\ndemographics, or ambiguous questions.",
                     text_color=MUTED,justify="left",font=ctk.CTkFont(size=11)).pack(anchor="w",padx=24)

        ctk.CTkLabel(side,text="DAILY AUTOMATION",text_color=CYAN,
                     font=ctk.CTkFont(size=12,weight="bold")).pack(anchor="w",padx=24,pady=(26,4))
        ctk.CTkLabel(side,text="03:00 PM EASTERN",text_color=TEXT).pack(anchor="w",padx=24)
        ctk.CTkLabel(side,textvariable=self.schedule,text_color=GREEN).pack(anchor="w",padx=24,pady=(0,8))
        ctk.CTkButton(side,text="ARM 3 PM SCHEDULE",command=self.install_schedule,
                      fg_color=PANEL2,border_width=1,border_color=CYAN,text_color=CYAN,
                      hover_color="#102638").pack(fill="x",padx=24,pady=4)
        ctk.CTkButton(side,text="DISARM SCHEDULE",command=self.remove_schedule,
                      fg_color="transparent",border_width=1,border_color="#31424D",
                      text_color=MUTED,hover_color="#101820").pack(fill="x",padx=24,pady=4)

        ctk.CTkLabel(side,text="SYSTEM STATUS",text_color=CYAN,
                     font=ctk.CTkFont(size=12,weight="bold")).pack(anchor="w",padx=24,pady=(24,4))
        ctk.CTkLabel(side,textvariable=self.status,text_color=GREEN,wraplength=235,justify="left").pack(anchor="w",padx=24)

        main=ctk.CTkFrame(self,fg_color=BG)
        main.grid(row=0,column=1,sticky="nsew",padx=20,pady=18)
        main.grid_columnconfigure(0,weight=1)
        main.grid_rowconfigure(2,weight=1)

        top=ctk.CTkFrame(main,fg_color="transparent")
        top.grid(row=0,column=0,sticky="ew")
        top.grid_columnconfigure((0,1,2,3),weight=1)
        self.resume_card=self.card(top,"Resume","NOT LOADED",0,0)
        self.jobs_card=self.card(top,"Tracked Jobs","0",0,1)
        self.apply_card=self.card(top,"Apply Queue","0",0,2)
        self.last_card=self.card(top,"Last Scan",self.last_run.get(),0,3)

        tabs=ctk.CTkTabview(main,fg_color=PANEL,segmented_button_fg_color=PANEL2,
                           segmented_button_selected_color=CYAN2,
                           segmented_button_selected_hover_color=CYAN,
                           segmented_button_unselected_color=PANEL2,
                           text_color=TEXT,corner_radius=14)
        tabs.grid(row=2,column=0,sticky="nsew",pady=(12,0))
        dash=tabs.add("MISSION CONTROL")
        prof=tabs.add("IDENTITY PROFILE")
        track=tabs.add("JOB INTEL")
        self.build_dash(dash)
        self.build_profile(prof)
        self.build_tracker(track)

    def build_dash(self,p):
        p.grid_columnconfigure(0,weight=1); p.grid_rowconfigure(2,weight=1)
        ctk.CTkLabel(p,text="TOP REMOTE MATCHES • HIGH-DISCOVERY MODE",text_color=CYAN,
                     font=ctk.CTkFont(size=16,weight="bold")).grid(row=0,column=0,sticky="w",padx=12,pady=(12,6))
        self.resume_label=ctk.CTkLabel(p,text=self.resume_path or "NO RESUME LOADED",
                                       text_color=MUTED,anchor="w")
        self.resume_label.grid(row=1,column=0,sticky="ew",padx=12,pady=(0,8))
        self.best_box=ctk.CTkTextbox(p,fg_color="#050A11",text_color=TEXT,border_width=1,
                                     border_color="#183748",corner_radius=10,font=("Consolas",12),wrap="none")
        self.best_box.grid(row=2,column=0,sticky="nsew",padx=12,pady=(0,12))
        self.best_box.configure(state="disabled")

    def build_profile(self,p):
        p.grid_columnconfigure(1,weight=1)
        for r,(label,key) in enumerate([
            ("FIRST NAME","first_name"),("LAST NAME","last_name"),("EMAIL","email"),
            ("PHONE","phone"),("LOCATION","location"),("LINKEDIN","linkedin"),("PORTFOLIO","portfolio")
        ]):
            ctk.CTkLabel(p,text=label,text_color=MUTED,font=ctk.CTkFont(size=11,weight="bold")).grid(row=r,column=0,sticky="w",padx=18,pady=8)
            ctk.CTkEntry(p,textvariable=self.profile[key],fg_color="#07111B",border_color="#1D4A5A",
                         text_color=TEXT,height=38).grid(row=r,column=1,sticky="ew",padx=18,pady=8)
        self.neon_button(p,"SAVE IDENTITY PROFILE",self.save_profile).grid(row=8,column=1,sticky="e",padx=18,pady=18)

    def build_tracker(self,p):
        p.grid_columnconfigure(0,weight=1); p.grid_rowconfigure(1,weight=1)
        bar=ctk.CTkFrame(p,fg_color="transparent")
        bar.grid(row=0,column=0,sticky="ew",padx=12,pady=10)
        self.neon_button(bar,"REFRESH INTEL",self.refresh_jobs).pack(side="left",padx=(0,8))
        self.neon_button(bar,"APPLY TO URL",self.apply_selected,GREEN).pack(side="left")
        self.tracker_box=ctk.CTkTextbox(p,fg_color="#050A11",text_color=TEXT,border_width=1,
                                        border_color="#183748",corner_radius=10,font=("Consolas",12),wrap="none")
        self.tracker_box.grid(row=1,column=0,sticky="nsew",padx=12,pady=(0,12))
        self.tracker_box.configure(state="disabled")

    def save_profile(self):
        self.save_settings(); self.status.set("IDENTITY PROFILE SAVED")

    def upload_resume(self):
        path=filedialog.askopenfilename(title="Select Resume",
            filetypes=[("Resume files","*.pdf *.docx *.txt"),("PDF","*.pdf"),("Word","*.docx"),("Text","*.txt")])
        if not path:return
        try:
            text=extract_resume_text(LocalUpload(path))
            if not text.strip(): raise ValueError("Could not extract text from this resume.")
            self.resume_text=text
            RESUME_CACHE.write_text(text,encoding="utf-8")
            ext=Path(path).suffix.lower()
            cached=APP_DIR/f"resume{ext}"
            cached.write_bytes(Path(path).read_bytes())
            self.resume_path=str(cached)
            self.resume_label.configure(text=self.resume_path)
            self.resume_card.configure(text=Path(self.resume_path).name.upper())
            self.status.set("RESUME ONLINE")
            self.save_settings()
        except Exception as e:
            messagebox.showerror("Resume Error",str(e))

    def install_schedule(self):
        ok,msg=install_daily_task()
        if ok:
            self.schedule.set("ARMED"); self.status.set("3 PM AUTOMATION ARMED")
        else: messagebox.showerror("Schedule Error",msg or "Could not install schedule.")

    def remove_schedule(self):
        ok,msg=remove_daily_task()
        if ok:
            self.schedule.set("OFFLINE"); self.status.set("SCHEDULE DISARMED")
        else: messagebox.showerror("Schedule Error",msg or "Could not remove schedule.")

    def run_now(self):
        if not self.resume_text.strip():
            messagebox.showwarning("Resume Required","Upload your resume first."); return
        self.status.set("DEEP SCANNING REMOTE JOB NETWORKS...")
        threading.Thread(target=self._run_worker,daemon=True).start()

    def _run_worker(self):
        try:
            result=run_job_search(self.resume_text)
            self.after(0,lambda:self._complete(result))
        except Exception as e:
            details=traceback.format_exc()
            self.after(0,lambda:messagebox.showerror("Scan Error",f"{e}\n\n{details}"))

    def _complete(self,r):
        self.last_run.set(r["timestamp"])
        self.last_card.configure(text=r["timestamp"])
        self.status.set(f"SCAN COMPLETE • {r['fetched']} FOUND • {r['added']} NEW")
        self.save_settings()
        self.refresh_jobs()
        if r.get("errors"):
            messagebox.showwarning("Source Warnings","\n".join(r["errors"]))

    def profile_dict(self):
        d={k:v.get().strip() for k,v in self.profile.items()}
        d["full_name"]=(d["first_name"]+" "+d["last_name"]).strip()
        return d

    def apply_selected(self):
        url=simpledialog.askstring("CB Jobs","Paste the application URL:")
        if not url:return
        if not self.resume_path or not Path(self.resume_path).exists():
            messagebox.showwarning("Resume Required","Upload your resume first."); return
        self.status.set("OPENING APPLICATION CHANNEL...")
        def worker():
            try:
                res=apply_to_job(url,self.profile_dict(),self.resume_path,
                                 auto_submit=bool(self.auto_apply.get()),headless=False)
                self.after(0,lambda:self._apply_done(res))
            except Exception as e:
                self.after(0,lambda:messagebox.showerror("Auto Apply Error",str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_done(self,r):
        self.status.set(r["status"].upper())
        msg=r.get("message","")
        if r.get("blockers"): msg += "\n\nStopped for:\n" + "\n".join(r["blockers"])
        messagebox.showinfo("CB Jobs",msg or r["status"])

    def refresh_jobs(self):
        try:
            jobs=get_jobs()
            if jobs.empty:
                count=applyq=0
                text="NO JOB INTEL YET\n\nUPLOAD RESUME → RUN NOW"
            else:
                if "remote_verified" in jobs.columns: jobs=jobs[jobs["remote_verified"]==1]
                count=len(jobs)
                applyq=int((jobs["bucket"]=="Apply Queue").sum()) if "bucket" in jobs.columns else 0
                best=jobs.sort_values("match_score",ascending=False).head(40)
                lines=[]
                for _,r in best.iterrows():
                    lines.append(
                        f"[{int(r['match_score']):03d}%]  {str(r['bucket']).upper():<12}  "
                        f"{r['company']}  //  {r['title']}  //  {r.get('source','')}\n"
                        f"       {r['location']}  //  {r['url']}\n"
                    )
                text="\n".join(lines)
            self.jobs_card.configure(text=str(count))
            self.apply_card.configure(text=str(applyq))
            for box in (self.best_box,self.tracker_box):
                box.configure(state="normal"); box.delete("1.0","end"); box.insert("1.0",text); box.configure(state="disabled")
        except Exception as e:
            self.status.set(f"TRACKER ERROR: {e}")

def autorun():
    if not RESUME_CACHE.exists(): return 2
    run_job_search(RESUME_CACHE.read_text(encoding="utf-8",errors="ignore"))
    return 0

if __name__=="__main__":
    if "--autorun" in sys.argv: raise SystemExit(autorun())
    App().mainloop()
