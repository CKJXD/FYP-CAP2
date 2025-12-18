import customtkinter as ctk
from tkinter import filedialog, ttk
import pandas as pd
import ctypes
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re

# ===================== Core Logic =====================
BASE_INDUSTRY = "food"

INDUSTRY_KEYWORDS = {
    "food": {"food", "cafe", "restaurant", "eatery", "bakery", "drink", "grocer", "catering"},
    "construction": {"cement", "steel", "hardware", "concrete", "construction", "builder"},
    "healthcare": {"clinic", "hospital", "medical", "pharma", "health"},
    "logistics": {"transport", "delivery", "freight", "courier"},
    "education": {"school", "college", "academy", "training", "tuition"},
}

def moneyfy(x):
    try:
        if pd.isna(x):
            return 0.0
        s = str(x).replace(",", "").strip()
        if s.startswith("(") and s.endswith(")"):
            return -float(s[1:-1])
        return float(s) if s else 0.0
    except:
        return 0.0

def get_counterparty(desc):
    if not isinstance(desc, str):
        return "UNKNOWN"
    m = re.search(
        r"([A-Za-z0-9 &\.-]+(?:SDN BHD|BERHAD|PLT|ENTERPRISE|TRADING|HOLDINGS|CAFE|CENTRE|SENDIRIAN))",
        desc, re.I
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip().upper()
    parts = re.sub(r"[^A-Za-z0-9 ]", " ", desc).split()
    return " ".join(parts[:4]).upper() if parts else "UNKNOWN"

def detect_other_industries(desc):
    if not isinstance(desc, str):
        return set()
    s = desc.lower()
    return {ind for ind, kws in INDUSTRY_KEYWORDS.items() if any(k in s for k in kws)}

def find_col(cols, include_any=(), include_all=(), exclude_any=()):
    cols_l = [c.lower().strip() for c in cols]
    for orig, c in zip(cols, cols_l):
        if exclude_any and any(x in c for x in exclude_any):
            continue
        if include_all and not all(x in c for x in include_all):
            continue
        if include_any and not any(x in c for x in include_any):
            continue
        return orig
    return None

# ===================== Policy Matrix (Bank Actions) =====================
# "rule_id" drives the bank action mapping in a consistent & explainable way.
POLICY_MATRIX = {
    "INCOME_CONCENTRATION": {
        "action_level": "Enhanced Review",
        "action": (
            "Assess income concentration risk and apply a haircut/discount to this income source "
            "when calculating sustainable income and affordability."
        )
    },
    "INDUSTRY_MISMATCH": {
        "action_level": "Clarification Required",
        "action": (
            "Request clarification and supporting documents (e.g., invoices, contracts, delivery proof) "
            "to verify whether inflows represent genuine operating revenue. Consider excluding non-core inflows."
        )
    },
    "ROUND_AMOUNT_PATTERN": {
        "action_level": "Cash Flow Normalization",
        "action": (
            "Perform cash flow normalization by excluding unusually round or repetitive transactions. "
            "Review for potential fund cycling or related-party transfers."
        )
    },
    "ESCALATE_HIGH": {
        "action_level": "Escalate",
        "action": (
            "Escalate to Credit Risk / Compliance for enhanced due diligence before proceeding with any lending decision."
        )
    },
    "MONITOR_MEDIUM": {
        "action_level": "Monitor",
        "action": (
            "Obtain additional explanation and monitor closely before fully recognizing this income as sustainable."
        )
    },
    "STANDARD_SAFE": {
        "action_level": "Standard",
        "action": "No immediate action required. Continue standard monitoring."
    }
}

def build_policy_actions(risk: str, rule_ids: list[str]) -> tuple[str, str]:
    """
    Returns (action_level, actions_text) based on rule_ids and overall risk.
    - action_level: one short label
    - actions_text: concatenated recommended actions
    """

    # Collect policy items from rule_ids
    items = []
    for rid in rule_ids:
        if rid in POLICY_MATRIX:
            items.append(POLICY_MATRIX[rid])

    # Add risk-based escalation/monitoring
    if risk == "High":
        items.append(POLICY_MATRIX["ESCALATE_HIGH"])
    elif risk == "Medium":
        items.append(POLICY_MATRIX["MONITOR_MEDIUM"])
    else:
        items.append(POLICY_MATRIX["STANDARD_SAFE"])

    # Decide a single "action_level" priority (highest wins)
    priority = {
        "Escalate": 5,
        "Cash Flow Normalization": 4,
        "Enhanced Review": 3,
        "Clarification Required": 2,
        "Monitor": 1,
        "Standard": 0
    }

    final_level = "Standard"
    actions = []
    seen = set()

    for it in items:
        lvl = it["action_level"]
        act = it["action"]
        if act not in seen:
            actions.append(act)
            seen.add(act)
        if priority.get(lvl, 0) > priority.get(final_level, 0):
            final_level = lvl

    return final_level, " ".join(actions)

# ===================== UI =====================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class BankAnalyzerApp(ctk.CTk):
    BG_MAIN = "#0B0F19"
    BG_SIDEBAR = "#111827"
    ACCENT = "#3B82F6"

    # Soft readable colors
    SUCCESS = "#4ADE80"
    WARNING = "#FACC15"
    DANGER  = "#F87171"

    def __init__(self):
        super().__init__()
        self.title("Bank Statement Analyzer Pro – SME Loan Fraud Detector")
        self.geometry("1600x900")
        self.minsize(1280, 720)

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.selected_files = []
        self._popup_open = False

        self._build_ui()

    def _build_ui(self):
        # Sidebar
        sidebar = ctk.CTkFrame(self, width=340, corner_radius=0, fg_color=self.BG_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="Bank Analyzer", font=ctk.CTkFont(size=26, weight="bold"), text_color="white")\
            .grid(row=0, column=0, padx=20, pady=(30,10), sticky="w")
        ctk.CTkLabel(sidebar, text="AI Fraud Detection Terminal", font=ctk.CTkFont(size=13), text_color="#9CA3AF")\
            .grid(row=1, column=0, padx=20, pady=(0,30), sticky="w")

        btn_style = {"height":46, "font":ctk.CTkFont(size=14, weight="bold"), "corner_radius":10}
        ctk.CTkButton(sidebar, text="Choose File",      command=self.choose_file,  fg_color=self.ACCENT,  **btn_style)\
            .grid(row=2, column=0, padx=20, pady=8, sticky="ew")
        ctk.CTkButton(sidebar, text="Add More Files",   command=self.add_file,     fg_color="#0EA5E9",    **btn_style)\
            .grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        ctk.CTkButton(sidebar, text="Run AI Analysis",  command=self.run_analysis, fg_color=self.SUCCESS, **btn_style)\
            .grid(row=4, column=0, padx=20, pady=8, sticky="ew")
        ctk.CTkButton(sidebar, text="Clear All",        command=self.reset_all,    fg_color=self.DANGER,  **btn_style)\
            .grid(row=5, column=0, padx=20, pady=8, sticky="ew")

        ctk.CTkLabel(sidebar, text="Selected Files", font=ctk.CTkFont(size=14, weight="bold"), text_color="white")\
            .grid(row=6, column=0, padx=20, pady=(30,5), sticky="w")
        self.file_listbox = ctk.CTkTextbox(sidebar, height=120)
        self.file_listbox.grid(row=7, column=0, padx=20, pady=(0,15), sticky="ew")

        ctk.CTkLabel(sidebar, text="AI Risk Alerts", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.WARNING)\
            .grid(row=8, column=0, padx=20, pady=(10,5), sticky="w")

        # Readable alert box (monospace + tags)
        self.alert_box = ctk.CTkTextbox(
            sidebar,
            height=280,
            font=("Consolas", 12),
            wrap="word"
        )
        self.alert_box.grid(row=9, column=0, padx=20, pady=(0,20), sticky="ew")

        self.alert_box.tag_config("high",   background="#FEE2E2", foreground="#7F1D1D")
        self.alert_box.tag_config("medium", background="#FEF3C7", foreground="#78350F")
        self.alert_box.tag_config("safe",   background="#DCFCE7", foreground="#14532D")
        self.alert_box.tag_config("muted",  foreground="#9CA3AF")

        self.alert_box.insert("end", "Ready. Upload CSV bank statements and click 'Run AI Analysis'.\n", "muted")

        # Main area
        main = ctk.CTkFrame(self, fg_color=self.BG_MAIN)
        main.grid(row=0, column=1, sticky="nswe", padx=(0,10), pady=10)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # KPI row
        kpi_frame = ctk.CTkFrame(main, fg_color="transparent")
        kpi_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        for i in range(3):
            kpi_frame.grid_columnconfigure(i, weight=1)

        self.kpi_in  = self._kpi("Total Inflow",  "RM 0.00", kpi_frame, 0)
        self.kpi_out = self._kpi("Total Outflow", "RM 0.00", kpi_frame, 1)
        self.kpi_net = self._kpi("Net Position",  "RM 0.00", kpi_frame, 2, green=True)

        # Chart row
        chart_frame = ctk.CTkFrame(main, fg_color="white", corner_radius=16)
        chart_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        chart_frame.grid_columnconfigure(0, weight=3)
        chart_frame.grid_columnconfigure(1, weight=1)
        chart_frame.grid_rowconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(6,6), dpi=100)
        self.fig.patch.set_facecolor("white")
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nswe", padx=(20,10), pady=20)

        self.legend_label = ctk.CTkLabel(
            chart_frame,
            text="Upload files and run analysis...",
            text_color="#4B5563",
            justify="left",
            wraplength=300
        )
        self.legend_label.grid(row=0, column=1, sticky="nw", padx=20, pady=30)

        # Table
        table_frame = ctk.CTkFrame(main, fg_color="white", corner_radius=16)
        table_frame.grid(row=2, column=0, sticky="nswe", padx=10, pady=(0,10))
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            table_frame,
            text="Top 5 Inflow Companies – AI Risk Assessment",
            text_color="#111827",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(15,10), sticky="w")

        cols = ("Rank","Company","Inflow (RM)","%","Risk","Reason")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for c,w in zip(cols, [60,300,140,80,100,420]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center" if c not in ["Company","Reason"] else "w")
        self.tree.grid(row=1, column=0, sticky="nswe", padx=20, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="white", rowheight=40, font=("Segoe UI",11))
        style.configure("Treeview.Heading", font=("Segoe UI",12,"bold"), background="#F3F4F6")
        style.map("Treeview", background=[("selected","#DBEAFE")])
        self.tree.tag_configure("high",   background="#FECACA")
        self.tree.tag_configure("medium", background="#FEF3C7")
        self.tree.tag_configure("safe",   background="#D1FAE5")

    def _kpi(self, title, value, parent, col, green=False):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=12, border_width=1, border_color="#E5E7EB")
        card.grid(row=0, column=col, padx=10, pady=8, sticky="nsew")
        ctk.CTkLabel(card, text=title, text_color="#6B7280", font=ctk.CTkFont(size=13)).pack(padx=20, pady=(15,5), anchor="w")
        lbl = ctk.CTkLabel(card, text=value, text_color=self.SUCCESS if green else "#111827", font=ctk.CTkFont(size=26, weight="bold"))
        lbl.pack(padx=20, pady=(0,15), anchor="w")
        return lbl

    # --------------------- File handlers ---------------------
    def choose_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if f:
            self.selected_files = [f]
            self._update_file_list()

    def add_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if f and f not in self.selected_files:
            self.selected_files.append(f)
            self._update_file_list()

    def _update_file_list(self):
        self.file_listbox.delete("1.0", "end")
        for i, path in enumerate(self.selected_files, 1):
            name = path.split("/")[-1].split("\\")[-1]
            self.file_listbox.insert("end", f"{i}. {name}\n")

    def reset_all(self):
        self.selected_files.clear()
        self.file_listbox.delete("1.0", "end")

        self.alert_box.delete("1.0", "end")
        self.alert_box.insert("end", "Cleared. Ready for new analysis.\n", "muted")

        self.tree.delete(*self.tree.get_children())

        self.kpi_in.configure(text="RM 0.00")
        self.kpi_out.configure(text="RM 0.00")
        self.kpi_net.configure(text="RM 0.00", text_color=self.SUCCESS)

        self.ax.clear()
        self.canvas.draw()
        self.legend_label.configure(text="Upload files and run analysis...")

    # --------------------- Popup ---------------------
    def show_high_risk_popup(self, summary_text: str):
        if self._popup_open:
            return
        self._popup_open = True

        win = ctk.CTkToplevel(self)
        win.title("High Risk Alert")
        win.resizable(False, False)

        w, h = 520, 260
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        win.transient(self)
        win.grab_set()

        def close():
            try:
                win.grab_release()
            except:
                pass
            win.destroy()
            self._popup_open = False

        # Top bar with X
        top = ctk.CTkFrame(win, corner_radius=12)
        top.pack(fill="x", padx=12, pady=(12, 0))

        title = ctk.CTkLabel(top, text="HIGH RISK DETECTED", font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(side="left", padx=12, pady=10)

        btn_close = ctk.CTkButton(top, text="X", width=36, height=28, fg_color="#F87171", hover_color="#EF4444", command=close)
        btn_close.pack(side="right", padx=12, pady=10)

        body = ctk.CTkFrame(win, corner_radius=12)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        box = ctk.CTkTextbox(body, wrap="word", font=("Consolas", 12))
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("end", summary_text)
        box.configure(state="disabled")

        win.protocol("WM_DELETE_WINDOW", close)

    # --------------------- Alert renderer ---------------------
    def _render_alert_block(self, risk, company, pct, reason, action_level, actions):
        tag = "safe" if risk == "Safe" else ("medium" if risk == "Medium" else "high")
        divider = "-" * 58

        self.alert_box.insert("end", f"{risk.upper()} RISK\n", tag)
        self.alert_box.insert("end", f"Company      : {company}\n")
        self.alert_box.insert("end", f"Exposure (%) : {pct}%\n")
        self.alert_box.insert("end", f"Reason       : {reason}\n")
        self.alert_box.insert("end", f"Action Level : {action_level}\n")
        self.alert_box.insert("end", f"Actions      : {actions}\n")
        self.alert_box.insert("end", divider + "\n\n", "muted")

    # --------------------- Main analysis ---------------------
    def run_analysis(self):
        if not self.selected_files:
            self.alert_box.insert("end", "No file selected.\n", "muted")
            return

        dfs = []
        self.alert_box.delete("1.0", "end")

        for path in self.selected_files:
            try:
                df = pd.read_csv(path, encoding_errors="ignore")
                df.columns = [c.strip() for c in df.columns]

                desc_col = (
                    find_col(df.columns, include_any=("description",)) or
                    find_col(df.columns, include_any=("desc",)) or
                    find_col(df.columns, include_any=("transaction", "details")) or
                    find_col(df.columns, include_any=("narration",)) or
                    find_col(df.columns, include_any=("particular",))
                )

                credit_col = (
                    find_col(df.columns, include_any=("credit",)) or
                    find_col(df.columns, include_any=("deposit",)) or
                    find_col(df.columns, include_any=("cr",), exclude_any=("description", "desc")) or
                    find_col(df.columns, include_any=("inflow",)) or
                    find_col(df.columns, include_any=("in",), exclude_any=("date", "desc", "description", "transaction"))
                )

                debit_col = (
                    find_col(df.columns, include_any=("debit",)) or
                    find_col(df.columns, include_any=("withdraw",)) or
                    find_col(df.columns, include_any=("dr",), exclude_any=("description", "desc")) or
                    find_col(df.columns, include_any=("outflow",)) or
                    find_col(df.columns, include_any=("out",), exclude_any=("date", "desc", "description", "transaction"))
                )

                if not desc_col:
                    self.alert_box.insert("end", f"Skipped: {path.split('/')[-1]} (no description column found)\n", "muted")
                    continue

                df["desc"] = df[desc_col]
                df["credit"] = df[credit_col].apply(moneyfy) if credit_col else 0.0
                df["debit"]  = df[debit_col].apply(moneyfy) if debit_col else 0.0
                df["company"] = df["desc"].apply(get_counterparty)
                dfs.append(df)

            except Exception as e:
                self.alert_box.insert("end", f"Error reading {path.split('/')[-1]} -> {e}\n", "muted")

        if not dfs:
            self.alert_box.insert("end", "No valid data loaded. Please check your CSV format.\n", "muted")
            return

        data = pd.concat(dfs, ignore_index=True)

        total_in = float(data["credit"].sum())
        total_out = float(data["debit"].sum())
        net = total_in - total_out

        self.kpi_in.configure(text=f"RM {total_in:,.2f}")
        self.kpi_out.configure(text=f"RM {total_out:,.2f}")
        self.kpi_net.configure(text=f"RM {net:,.2f}", text_color=self.SUCCESS if net >= 0 else self.DANGER)

        if total_in <= 0:
            self.alert_box.insert("end", "No inflow transactions detected (credit = 0).\n", "muted")
            return

        top5 = (
            data[data["credit"] > 0]
            .groupby("company")["credit"].sum()
            .nlargest(5)
            .reset_index()
        )
        top5["pct"] = (top5["credit"] / total_in * 100).round(1)

        self.tree.delete(*self.tree.get_children())

        high_risk_companies = []

        for i, row in top5.iterrows():
            company = row["company"]
            pct = float(row["pct"])
            inflow_amt = float(row["credit"])

            txns = data[(data["company"] == company) & (data["credit"] > 0)]

            # ---- Rule detection (assign rule_ids) ----
            rule_ids = []
            flags = []

            # Rule A: Concentration risk
            if pct >= 30:
                rule_ids.append("INCOME_CONCENTRATION")
                flags.append("Income heavily depends on one company (>30%)")

            # Rule B: Industry mismatch vs base industry
            mismatch = False
            for d in txns["desc"].astype(str).tolist():
                inds = detect_other_industries(d)
                if inds and (BASE_INDUSTRY not in inds):
                    mismatch = True
                    break
            if mismatch:
                rule_ids.append("INDUSTRY_MISMATCH")
                flags.append("Source looks unrelated to your business industry")

            # Rule C: Round amount pattern (based on individual credits)
            round_pattern = any((abs(c) % 10000 == 0) or (abs(c) % 5000 == 0) for c in txns["credit"].tolist() if c > 0)
            if round_pattern:
                rule_ids.append("ROUND_AMOUNT_PATTERN")
                flags.append("Many inflows are very round numbers (possible manual adjustments)")

            # Risk label
            risk = "Safe" if not flags else ("Medium" if len(flags) == 1 else "High")
            reason = "; ".join(flags) if flags else "No unusual patterns detected"

            # Policy Matrix output
            action_level, actions = build_policy_actions(risk, rule_ids)

            # Table
            tag = "safe" if risk == "Safe" else ("medium" if risk == "Medium" else "high")
            self.tree.insert(
                "", "end",
                values=(i + 1, company, f"RM {inflow_amt:,.2f}", f"{pct}%", risk, reason),
                tags=(tag,)
            )

            # Alerts (now includes actions)
            self._render_alert_block(risk, company, pct, reason, action_level, actions)

            if risk == "High":
                high_risk_companies.append((company, pct, action_level))

        # High risk popup (centered)
        if high_risk_companies:
            lines = []
            lines.append("One or more HIGH RISK inflow sources were detected.\n")
            lines.append("Recommended: Escalate for enhanced due diligence before proceeding.\n")
            lines.append("High Risk Summary:\n")
            for c, p, lvl in high_risk_companies:
                lines.append(f"- {c} | Exposure: {p}% | Action Level: {lvl}")
            lines.append("\nTip: Check AI Risk Alerts panel for detailed reasons and actions.")
            self.show_high_risk_popup("\n".join(lines))

        # Pie chart
        self.ax.clear()
        colors = ["#3B82F6", "#4ADE80", "#FACC15", "#F87171", "#8B5CF6"]
        self.ax.pie(
            top5["credit"],
            labels=top5["company"],
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
            textprops=dict(color="white", weight="bold")
        )
        self.ax.set_title("Top 5 Inflow Sources", fontsize=16, color="#111827")
        self.canvas.draw()

        legend = "\n".join([f"• {r['company']}: RM {float(r['credit']):,.0f} ({float(r['pct'])}%)" for _, r in top5.iterrows()])
        self.legend_label.configure(text=legend)

# --------------------- Start ---------------------
if __name__ == "__main__":
    app = BankAnalyzerApp()
    app.mainloop()
