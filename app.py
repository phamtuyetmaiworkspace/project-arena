import os
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Project Arena", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

CATEGORIES = ["Communication", "Business", "Public", "Social"]
CATEGORY_LABELS = {
    "Communication": "Dự án Truyền thông",
    "Business": "Dự án Kinh doanh",
    "Public": "Dự án Công",
    "Social": "Dự án Xã hội",
}
CATEGORY_ICONS = {
    "Communication": "◉",
    "Business": "◆",
    "Public": "⬡",
    "Social": "✦",
}
# Official dates, categories and project order from the final pitching lists.
PITCHING_SCHEDULE = {
    "E.032.03_1": [
        ("10/11/2026", "Public", ["G03", "G04", "G13", "G15"]),
        ("10/11/2026", "Social", ["G02", "G09", "G10", "G14"]),
        ("17/11/2026", "Business", ["G01", "G05", "G11", "G16"]),
        ("17/11/2026", "Communication", ["G06", "G07", "G08", "G12"]),
    ],
    "E.032.03_2": [
        ("10/11/2026", "Communication", ["G03", "G05", "G09"]),
        ("10/11/2026", "Business", ["G02", "G07", "G08"]),
        ("17/11/2026", "Public", ["G01", "G10"]),
        ("17/11/2026", "Social", ["G04", "G06", "G11"]),
    ],
}


def ordered_categories(server_id):
    return [c for _, c, _ in PITCHING_SCHEDULE.get(server_id, [])] or CATEGORIES


def project_sort_key(server_id, project):
    for index, (_, _, codes) in enumerate(PITCHING_SCHEDULE.get(server_id, [])):
        if project.get("project_code") in codes:
            return (index, codes.index(project["project_code"]))
    return (99, project.get("project_code", ""))


DEFAULT_BUDGET = 100_000_000
CLASS_BUDGETS = {"E.032.03_1": 150_000_000}


def student_budget(server_id):
    return CLASS_BUDGETS.get(server_id, DEFAULT_BUDGET)
MAX_PER_PROJECT = 25_000_000

# =========================
# STYLE
# =========================
st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(circle at 10% 10%, rgba(80,45,180,.18), transparent 28%),
          radial-gradient(circle at 88% 12%, rgba(0,200,255,.12), transparent 26%),
          linear-gradient(180deg, #070A12 0%, #0A1020 58%, #070A12 100%);
      }
      .block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
      h1,h2,h3 {letter-spacing: .02em;}
      .arena-hero {
        border: 1px solid rgba(124,92,255,.35);
        border-radius: 24px;
        padding: 24px 28px;
        background: linear-gradient(135deg, rgba(18,25,45,.86), rgba(15,22,42,.56));
        box-shadow: 0 0 36px rgba(90,70,255,.10), inset 0 0 22px rgba(255,255,255,.02);
        margin-bottom: 18px;
      }
      .arena-title {
        font-size: 2.15rem; font-weight: 800; margin: 0;
        background: linear-gradient(90deg,#F8FBFF,#98E9FF,#B39CFF);
        -webkit-background-clip: text; color: transparent;
      }
      .arena-sub {color:#AAB6D3; margin-top:7px;}
      .metric-card {
        border:1px solid rgba(255,255,255,.08);
        border-radius:20px; padding:18px 20px;
        background:rgba(17,24,43,.72);
        min-height:118px;
      }
      .metric-label {font-size:.78rem;color:#8290B2;text-transform:uppercase;letter-spacing:.12em;}
      .metric-value {font-size:1.55rem;font-weight:750;color:#F4F7FF;margin-top:8px;}
      .chip {
        display:inline-block;padding:6px 10px;border-radius:999px;
        border:1px solid rgba(117,219,255,.25); color:#A9EDFF;background:rgba(65,170,255,.08);
        margin-right:6px;font-size:.82rem;
      }
      .project-card {
        border:1px solid rgba(255,255,255,.08);
        border-radius:18px;padding:16px 18px;background:rgba(16,23,42,.82);margin-bottom:10px;
      }
      .project-code {color:#8FA0C8;font-size:.8rem;letter-spacing:.12em;}
      .project-name {font-size:1.2rem;font-weight:700;color:#F4F7FF;margin-top:4px;}
      .muted {color:#8794B5;}
      .ok {color:#8EF0C0;font-weight:650;}
      .warn {color:#FFD27D;font-weight:650;}
      div[data-testid="stDataFrame"] {border:1px solid rgba(255,255,255,.07);border-radius:16px;overflow:hidden;}
      .stButton>button {border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# DATABASE
# =========================
@st.cache_resource
def get_db():
    url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))
    if not url or not key:
        return None
    return create_client(url, key)


def require_db():
    db = get_db()
    if db is None:
        st.error("Chưa cấu hình Supabase. Xem README.md để thêm SUPABASE_URL và SUPABASE_KEY.")
        st.stop()
    return db


def q(table, select="*", **eqs):
    db = require_db()
    query = db.table(table).select(select)
    for k, v in eqs.items():
        query = query.eq(k, v)
    return query.execute().data or []


def log_event(server_id, actor, action, details=None):
    require_db().table("audit_logs").insert({
        "server_id": server_id,
        "actor": actor,
        "action": action,
        "details": details or {},
    }).execute()


def format_money(v):
    v = float(v or 0)
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    return f"{v/1_000_000:.0f}M"


def get_student(server_id, student_id):
    rows = q("students", "*", server_id=server_id, student_id=student_id)
    return rows[0] if rows else None


def get_project(project_id):
    rows = q("projects", "*", id=project_id)
    return rows[0] if rows else None


def get_round(server_id):
    rows = q("round_state", "*", server_id=server_id)
    return rows[0] if rows else {"server_id": server_id, "status": "SETUP", "current_category": None}


def student_category(student):
    if not student or not student.get("project_id"):
        return None
    p = get_project(student["project_id"])
    return p.get("category") if p else None


def student_investments(student_uuid):
    return q("investments", "*", student_uuid=student_uuid)


def invested_total(student_uuid):
    return sum(float(x.get("amount") or 0) for x in student_investments(student_uuid))


def upsert_investment(server_id, student, project, amount, rationale):
    db = require_db()
    payload = {
        "server_id": server_id,
        "student_uuid": student["id"],
        "project_id": project["id"],
        "amount": amount,
        "rationale": rationale or None,
        "is_valid": True,
        "invalid_reason": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("investments").upsert(payload, on_conflict="server_id,student_uuid,project_id").execute()
    log_event(server_id, student["student_id"], "INVESTMENT_UPSERT", {"project": project["project_code"], "amount": amount})


# =========================
# HEADER / SESSION
# =========================
def hero(subtitle="Investment simulation for project pitching"):
    st.markdown(
        f"""
        <div class="arena-hero">
          <div class="arena-title">PROJECT ARENA</div>
          <div class="arena-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def logout():
    for k in ["role", "server_id", "student_id", "teacher_auth"]:
        st.session_state.pop(k, None)
    st.rerun()


# =========================
# LOGIN
# =========================
def login_screen():
    hero("Pitch. Allocate capital. Test project conviction.")
    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.markdown("### Student access")
        server = st.selectbox("Lớp tín chỉ", ["TEST", "E.032.03_1", "E.032.03_2", "E.032.03_3"], key="login_server")
        sid = st.text_input("Mã sinh viên", placeholder="VD: SV001")
        code = st.text_input("Mã đăng nhập (nếu được cấp)", type="password")
        if st.button("ENTER ARENA", use_container_width=True, type="primary"):
            student = get_student(server, sid.strip()) if sid.strip() else None
            if not student:
                st.error("Không tìm thấy sinh viên trong server đã chọn.")
            elif student.get("login_code") and code != student.get("login_code"):
                st.error("Mã đăng nhập không đúng.")
            else:
                st.session_state.role = "student"
                st.session_state.server_id = server
                st.session_state.student_id = sid.strip()
                st.rerun()
    with c2:
        st.markdown("### Teacher control")
        teacher_pass = st.text_input("Teacher password", type="password")
        teacher_server = st.selectbox("Lớp cần quản lý", ["TEST", "E.032.03_1", "E.032.03_2", "E.032.03_3"], key="teacher_server")
        if st.button("OPEN CONTROL ROOM", use_container_width=True):
            expected = st.secrets.get("TEACHER_PASSWORD", os.getenv("TEACHER_PASSWORD", "change-me"))
            if teacher_pass == expected:
                st.session_state.role = "teacher"
                st.session_state.server_id = teacher_server
                st.session_state.teacher_auth = True
                st.rerun()
            else:
                st.error("Teacher password không đúng.")


# =========================
# STUDENT APP
# =========================
def student_app():
    server_id = st.session_state.server_id
    student = get_student(server_id, st.session_state.student_id)
    if not student:
        st.error("Tài khoản không còn tồn tại.")
        logout()
        return

    round_state = get_round(server_id)
    my_project = get_project(student.get("project_id")) if student.get("project_id") else None
    my_cat = my_project.get("category") if my_project else None
    invs = student_investments(student["id"])
    spent = sum(float(x.get("amount") or 0) for x in invs)
    budget = student_budget(server_id)
    remaining = budget - spent

    hero(f"Lớp {server_id} · Investor Console")
    with st.sidebar:
        st.markdown(f"### {student['student_name']}")
        st.caption(student["student_id"])
        if my_project:
            st.write(f"**Nhóm:** {my_project['project_name']}")
            st.write(f"**Lĩnh vực:** {CATEGORY_LABELS[my_cat]}")
        else:
            st.warning("Chưa được gán vào dự án.")
        st.divider()
        st.write(f"**Đã đầu tư:** {format_money(spent)}")
        st.write(f"**Còn lại:** {format_money(remaining)}")
        st.progress(max(0.0, min(spent / budget, 1.0)))
        st.divider()
        if st.button("Đăng xuất"):
            logout()

    a, b, c = st.columns(3)
    with a:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Wallet</div><div class="metric-value">{format_money(remaining)}</div><div class="muted">còn lại / {format_money(budget)}</div></div>', unsafe_allow_html=True)
    with b:
        cur = round_state.get("current_category") or "—"
        label = CATEGORY_LABELS.get(cur, cur)
        st.markdown(f'<div class="metric-card"><div class="metric-label">Current round</div><div class="metric-value">{label}</div><div class="muted">{round_state.get("status")}</div></div>', unsafe_allow_html=True)
    with c:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Portfolio</div><div class="metric-value">{len(invs)} projects</div><div class="muted">max 25M / project</div></div>', unsafe_allow_html=True)

    st.markdown("### Current investment round")
    cur_cat = round_state.get("current_category")
    status = round_state.get("status")

    if not my_project:
        st.info("Teacher cần gán bạn vào một nhóm/dự án trước khi bạn có thể đầu tư.")
        return
    if status != "OPEN" or not cur_cat:
        st.info("Investment round hiện chưa mở. Hãy theo dõi hướng dẫn của giảng viên.")
    else:
        projects = sorted(q("projects", "*", server_id=server_id, category=cur_cat), key=lambda p: project_sort_key(server_id, p))
        if not projects:
            st.warning("Chưa có dự án trong round này.")
        for p in projects:
            if p["id"] == student.get("project_id"):
                st.info(f"Không thể đầu tư vào nhóm của mình: {p['project_code']}.")
                continue
            existing = next((x for x in invs if x["project_id"] == p["id"]), None)
            current_amount = int(float(existing.get("amount") or 0)) if existing else 0
            st.markdown(
                f"""
                <div class="project-card">
                  <div class="project-code">{p['project_code']} · {CATEGORY_ICONS[p['category']]} {CATEGORY_LABELS[p['category']]}</div>
                  <div class="project-name">{p['project_name']}</div>
                  <div class="muted">{p.get('one_liner') or 'Chưa có mô tả ngắn.'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns([1.3, 1.4, .8])
            with c1:
                amount_m = st.number_input(
                    f"Đầu tư (triệu) · {p['project_code']}", min_value=0, max_value=25,
                    value=int(current_amount/1_000_000), step=1, key=f"amt_{p['id']}"
                )
            with c2:
                rationale = st.selectbox(
                    f"Lý do · {p['project_code']}",
                    ["", "Feasibility", "Innovation", "Social/Public value", "Financial sustainability", "Pitch quality"],
                    key=f"why_{p['id']}"
                )
            with c3:
                st.write("")
                st.write("")
                if st.button("SAVE", key=f"save_{p['id']}", use_container_width=True):
                    new_amount = amount_m * 1_000_000
                    other_total = spent - current_amount
                    if new_amount > MAX_PER_PROJECT:
                        st.error("Tối đa 25M cho một dự án.")
                    elif other_total + new_amount > budget:
                        st.error(f"Vượt tổng ngân sách {format_money(budget)}.")
                    elif new_amount == 0:
                        if existing:
                            require_db().table("investments").delete().eq("id", existing["id"]).execute()
                            log_event(server_id, student["student_id"], "INVESTMENT_DELETE", {"project": p["project_code"]})
                            st.success("Đã xóa khoản đầu tư.")
                            st.rerun()
                    else:
                        upsert_investment(server_id, student, p, new_amount, rationale)
                        st.success("Đã lưu khoản đầu tư.")
                        st.rerun()

    st.markdown("### My portfolio")
    if not invs:
        st.caption("Chưa có khoản đầu tư nào.")
    else:
        proj_map = {p["id"]: p for p in q("projects", "*")}
        rows = []
        for x in invs:
            p = proj_map.get(x["project_id"], {})
            rows.append({
                "Project": p.get("project_name", "?"),
                "Category": CATEGORY_LABELS.get(p.get("category"), p.get("category")),
                "Amount": format_money(x.get("amount")),
                "Reason": x.get("rationale") or "—",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# =========================
# TEACHER HELPERS
# =========================
def import_students(server_id, uploaded):
    df = pd.read_csv(uploaded)
    required = {"student_id", "student_name"}
    if not required.issubset(df.columns):
        st.error("CSV cần tối thiểu cột student_id và student_name.")
        return
    db = require_db()
    count = 0
    for _, r in df.iterrows():
        row_server = str(r.get("server_id", server_id)).strip() or server_id
        if row_server != server_id:
            continue
        payload = {
            "server_id": server_id,
            "student_id": str(r["student_id"]).strip(),
            "student_name": str(r["student_name"]).strip(),
            "login_code": None if pd.isna(r.get("login_code")) or str(r.get("login_code", "")).strip()=="" else str(r.get("login_code")).strip(),
        }
        db.table("students").upsert(payload, on_conflict="server_id,student_id").execute()
        count += 1
    log_event(server_id, "TEACHER", "IMPORT_STUDENTS", {"count": count})
    st.success(f"Đã import/update {count} sinh viên vào lớp {server_id}.")


def reciprocal_flags(server_id):
    students = q("students", "*", server_id=server_id)
    projects = sorted(q("projects", "*", server_id=server_id), key=lambda p: project_sort_key(server_id, p))
    invs = q("investments", "*", server_id=server_id)
    st_by_id = {s["id"]: s for s in students}
    p_by_id = {p["id"]: p for p in projects}
    flow = {}
    for x in invs:
        s = st_by_id.get(x["student_uuid"])
        target = p_by_id.get(x["project_id"])
        if not s or not target or not s.get("project_id"):
            continue
        source_project = s["project_id"]
        key = (source_project, target["id"])
        flow[key] = flow.get(key, 0) + float(x.get("amount") or 0)
    flags = []
    seen = set()
    for (a,b), ab in flow.items():
        if (b,a) in flow and frozenset([a,b]) not in seen:
            ba = flow[(b,a)]
            pa, pb = p_by_id.get(a), p_by_id.get(b)
            if pa and pb:
                flags.append({
                    "Team A": pa["project_name"], "A → B": format_money(ab),
                    "Team B": pb["project_name"], "B → A": format_money(ba),
                    "Reciprocal": format_money(min(ab, ba)),
                })
                seen.add(frozenset([a,b]))
    return flags


def compute_results(server_id):
    projects = q("projects", "*", server_id=server_id)
    invs = q("investments", "*", server_id=server_id)
    students = q("students", "*", server_id=server_id)
    pmap = {p["id"]: p for p in projects}
    smap = {s["id"]: s for s in students}

    funding = {}
    investors = {}
    for x in invs:
        if not x.get("is_valid", True):
            continue
        pid = x["project_id"]
        funding[pid] = funding.get(pid, 0) + float(x.get("amount") or 0)
        investors.setdefault(pid, set()).add(x["student_uuid"])

    project_rows = []
    for p in projects:
        project_rows.append({
            "id": p["id"], "Code": p["project_code"], "Project": p["project_name"],
            "Category": p["category"], "Funding": funding.get(p["id"], 0),
            "Investors": len(investors.get(p["id"], set())), "Final Score": p.get("final_score")
        })

    investor_rows = []
    for s in students:
        sinvs = [x for x in invs if x["student_uuid"] == s["id"] and x.get("is_valid", True)]
        total = sum(float(x.get("amount") or 0) for x in sinvs)
        weighted = 0.0
        scored_capital = 0.0
        for x in sinvs:
            p = pmap.get(x["project_id"])
            if p and p.get("final_score") is not None:
                amt = float(x.get("amount") or 0)
                weighted += amt * float(p["final_score"])
                scored_capital += amt
        quality = weighted / scored_capital if scored_capital > 0 else None
        investor_rows.append({
            "Student": s["student_name"], "Student ID": s["student_id"],
            "Invested": total, "Investment Quality": quality,
        })
    return pd.DataFrame(project_rows), pd.DataFrame(investor_rows)


def round_export_frames(server_id, category):
    """Fresh, server-scoped export; invalid entries are retained and marked."""
    projects = q("projects", "*", server_id=server_id, category=category)
    pmap = {p["id"]: p for p in projects}
    students = {s["id"]: s for s in q("students", "*", server_id=server_id)}
    project_ids = set(pmap)
    invs = [
        x for x in q("investments", "*", server_id=server_id)
        if x.get("project_id") in project_ids
    ]
    rows = []
    for x in invs:
        p = pmap[x["project_id"]]
        student = students.get(x.get("student_uuid"), {})
        rows.append({
            "Lop": server_id,
            "Linh vuc": CATEGORY_LABELS[category],
            "Nhom": p["project_code"],
            "Du an": p["project_name"],
            "MSSV": student.get("student_id", ""),
            "Ho ten": student.get("student_name", ""),
            "So von (VND)": float(x.get("amount") or 0),
            "Hop le": bool(x.get("is_valid", True)),
            "Ly do khong hop le": x.get("invalid_reason") or "",
            "Ly do dau tu": x.get("rationale") or "",
            "Thoi gian tao": x.get("created_at") or "",
            "Thoi gian cap nhat": x.get("updated_at") or "",
        })
    detail_columns = [
        "Lop", "Linh vuc", "Nhom", "Du an", "MSSV", "Ho ten",
        "So von (VND)", "Hop le", "Ly do khong hop le",
        "Ly do dau tu", "Thoi gian tao", "Thoi gian cap nhat",
    ]
    detail = pd.DataFrame(rows, columns=detail_columns)
    summary = []
    for p in sorted(projects, key=lambda x: project_sort_key(server_id, x)):
        valid = [
            x for x in invs if x["project_id"] == p["id"] and x.get("is_valid", True)
        ]
        summary.append({
            "Lop": server_id,
            "Linh vuc": CATEGORY_LABELS[category],
            "Nhom": p["project_code"],
            "Du an": p["project_name"],
            "Tong von hop le (VND)": sum(float(x.get("amount") or 0) for x in valid),
            "So nha dau tu": len({x["student_uuid"] for x in valid}),
            "So giao dich hop le": len(valid),
        })
    result = pd.DataFrame(summary)
    if not result.empty:
        result = result.sort_values(
            ["Tong von hop le (VND)", "So nha dau tu", "Nhom"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        result.insert(0, "Xep hang tam tinh", result.index + 1)
    return detail, result


# =========================
# LIVE RESULTS (TEACHER ONLY)
# =========================
@st.fragment(run_every="2s")
def live_results_panel(server_id):
    """Read fresh data each refresh; no investment or student identities exposed."""
    state = get_round(server_id)
    category = state.get("current_category")
    status = state.get("status", "SETUP")
    categories = [category] if category in CATEGORIES else CATEGORIES

    st.caption("Tự cập nhật mỗi 2 giây · Chỉ hiển thị trong Teacher Control Room")
    if not category:
        category = st.selectbox("Lĩnh vực theo dõi", CATEGORIES, key="live_category")
        categories = [category]
    st.markdown(f"**Vòng hiện tại:** {CATEGORY_LABELS.get(category, 'Chưa chọn')} · **{status}**")

    if status == "OPEN" and state.get("updated_at"):
        try:
            opened = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
            elapsed = max(0, int((datetime.now(timezone.utc) - opened).total_seconds()))
            remaining = max(0, 600 - elapsed)
            st.metric("Thời gian đầu tư tham khảo", f"{remaining // 60:02d}:{remaining % 60:02d}")
            if remaining == 0:
                st.warning("Đã hết 10 phút dự kiến. Giảng viên cần nhấn CLOSE ROUND để khóa đầu tư.")
        except (ValueError, TypeError):
            pass

    pdf, _ = compute_results(server_id)
    if pdf.empty:
        st.info("Chưa có dự án trong lớp này.")
        return
    current = pdf[pdf["Category"].isin(categories)].copy()
    if current.empty:
        st.info("Chưa có dự án trong lĩnh vực này.")
        return
    current = current.sort_values(["Funding", "Project"], ascending=[False, True])
    total_capital = float(current["Funding"].sum())
    active_investors = q("investments", "student_uuid,project_id,is_valid", server_id=server_id)
    selected_ids = set(current["id"].tolist())
    unique_investors = len({
        x["student_uuid"] for x in active_investors
        if x["project_id"] in selected_ids and x.get("is_valid", True)
    })
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng vốn huy động", f"{total_capital / 1_000_000:,.0f} triệu VND")
    c2.metric("Số nhà đầu tư", unique_investors)
    c3.metric("Số dự án", len(current))

    show = st.toggle("Hiện bảng xếp hạng trên màn hình", value=False, key="live_reveal")
    if not show:
        st.info("Kết quả đang được ẩn. Bật công tắc sau khi đóng vòng để công bố.")
        return

    current.insert(0, "Rank", range(1, len(current) + 1))
    current["Funding (triệu VND)"] = current["Funding"] / 1_000_000
    st.dataframe(
        current[["Rank", "Code", "Project", "Funding (triệu VND)", "Investors"]],
        hide_index=True, use_container_width=True,
    )
    fig = px.bar(
        current, x="Project", y="Funding (triệu VND)", text="Funding (triệu VND)",
        hover_data=["Code", "Investors"],
    )
    fig.update_traces(texttemplate="%{text:,.0f}M", textposition="outside")
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", margin=dict(t=35),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"live_chart_{server_id}_{category}")


# =========================
# TEACHER APP
# =========================
def teacher_app():
    server_id = st.session_state.server_id
    hero(f"Lớp {server_id} · Teacher Control Room")
    with st.sidebar:
        st.markdown("### CONTROL ROOM")
        st.caption(f"Lớp tín chỉ {server_id}")
        st.write("**Rules**")
        st.write(f"• {format_money(student_budget(server_id))} / student")
        st.write("• max 25M / project")
        st.write("• no investment into your own team project")
        st.write("• category-by-category rounds")
        st.divider()
        if st.button("Đăng xuất"):
            logout()

    students = q("students", "*", server_id=server_id)
    projects = sorted(q("projects", "*", server_id=server_id), key=lambda p: project_sort_key(server_id, p))
    invs = q("investments", "*", server_id=server_id)
    round_state = get_round(server_id)

    c1,c2,c3,c4 = st.columns(4)
    metrics = [
        (c1, "Students", str(len(students)), "registered"),
        (c2, "Projects", str(len(projects)), "configured"),
        (c3, "Capital deployed", format_money(sum(float(x.get("amount") or 0) for x in invs)), "live database"),
        (c4, "Round status", round_state.get("status","—"), CATEGORY_LABELS.get(round_state.get("current_category"), round_state.get("current_category") or "No category")),
    ]
    for col,label,val,sub in metrics:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{val}</div><div class="muted">{sub}</div></div>', unsafe_allow_html=True)

    tabs = st.tabs(["01 · Setup", "02 · Round Control", "03 · Live Monitor", "04 · Results", "05 · Integrity"])

    # SETUP
    with tabs[0]:
        if PITCHING_SCHEDULE.get(server_id):
            st.markdown("### Lịch và thứ tự pitching chính thức")
            group_counts = {}
            for member in students:
                if member.get("project_id"):
                    pid = member["project_id"]
                    group_counts[pid] = group_counts.get(pid, 0) + 1
            by_code = {p["project_code"]: p for p in projects}
            plan = []
            for day, category, codes in PITCHING_SCHEDULE[server_id]:
                for number, code in enumerate(codes, 1):
                    p = by_code.get(code, {})
                    plan.append({
                        "Ngày": day, "Lĩnh vực": CATEGORY_LABELS[category],
                        "Thứ tự": number, "Nhóm": code,
                        "Tên dự án": p.get("project_name", "Chưa tạo"),
                        "Số thành viên đã gán": group_counts.get(p.get("id"), 0),
                    })
            st.dataframe(pd.DataFrame(plan), hide_index=True, use_container_width=True)
            st.divider()

        st.markdown("### Student import")
        up = st.file_uploader("CSV: student_id, student_name, optional server_id, login_code", type=["csv"])
        if up and st.button("IMPORT / UPDATE STUDENTS", type="primary"):
            import_students(server_id, up)
            st.rerun()
        if students:
            st.dataframe(pd.DataFrame(students)[["student_id","student_name","project_id"]], hide_index=True, use_container_width=True)

        st.divider()
        st.markdown("### Kiểm tra thành viên chưa được gán nhóm")
        unassigned = [s for s in students if not s.get("project_id")]
        st.metric("Số sinh viên cần xác minh nhóm", len(unassigned))
        if unassigned and projects:
            st.warning("Chỉ gán sinh viên sau khi xác minh được nhóm từ danh sách lớp.")
            student_opts = {f"{x['student_id']} · {x['student_name']}": x for x in unassigned}
            project_opts = {f"{p['project_code']} · {p['project_name']}": p for p in projects}
            with st.form("member_assignment"):
                student_choice = st.selectbox("Sinh viên", list(student_opts.keys()))
                project_choice = st.selectbox("Nhóm", list(project_opts.keys()))
                verified = st.checkbox("Đã xác minh thành viên thuộc nhóm này")
                if st.form_submit_button("GÁN NHÓM"):
                    if not verified:
                        st.error("Cần xác minh thành viên trước khi gán nhóm.")
                        st.stop()
                    student_to_assign = student_opts[student_choice]
                    target = project_opts[project_choice]
                    require_db().table("students").update({"project_id": target["id"]}).eq(
                        "id", student_to_assign["id"]).eq("server_id", server_id).execute()
                    log_event(server_id, "TEACHER", "ASSIGN_TEAM", {
                        "student_id": student_to_assign["student_id"],
                        "project": target["project_code"],
                    })
                    st.rerun()
            st.dataframe(pd.DataFrame(unassigned)[["student_id", "student_name"]],
                         hide_index=True, use_container_width=True)
        st.divider()
        st.markdown("### Project & team manager")
        with st.form("new_project"):
            a,b = st.columns(2)
            with a:
                code = st.text_input("Project code", placeholder="COM01")
                name = st.text_input("Project name")
                category = st.selectbox("Category", CATEGORIES, format_func=lambda x: CATEGORY_LABELS[x])
            with b:
                one_liner = st.text_area("One-line description", height=90)
                requested = st.number_input("Requested funding (million VND)", min_value=0, step=50)
            member_opts = {f"{s['student_id']} — {s['student_name']}": s["id"] for s in students}
            selected = st.multiselect("Team members", list(member_opts.keys()))
            create = st.form_submit_button("CREATE PROJECT")
            if create:
                if not code.strip() or not name.strip() or not selected:
                    st.error("Cần mã dự án, tên dự án và ít nhất 1 thành viên.")
                else:
                    db = require_db()
                    p = db.table("projects").insert({
                        "server_id": server_id, "project_code": code.strip(), "project_name": name.strip(),
                        "category": category, "one_liner": one_liner.strip() or None,
                        "requested_funding": requested * 1_000_000,
                    }).execute().data[0]
                    for label in selected:
                        db.table("students").update({"project_id": p["id"]}).eq("id", member_opts[label]).execute()
                    log_event(server_id, "TEACHER", "CREATE_PROJECT", {"code": code.strip(), "category": category})
                    st.success("Đã tạo dự án và gán thành viên.")
                    st.rerun()
        if projects:
            pview = pd.DataFrame(projects)[["project_code","project_name","category","one_liner","final_score"]]
            st.dataframe(pview, hide_index=True, use_container_width=True)

    # ROUND CONTROL
    with tabs[1]:
        st.markdown("### Pitching → Investment transition")
        scheduled = ordered_categories(server_id)
        selected_cat = st.selectbox(
            "Lĩnh vực", scheduled,
            index=scheduled.index(round_state["current_category"]) if round_state.get("current_category") in scheduled else 0,
            format_func=lambda x: CATEGORY_LABELS[x]
        )
        st.write("Quy trình khuyến nghị: **PITCHING** → tất cả nhóm trong lĩnh vực pitch xong → **OPEN INVESTMENT** → **CLOSE ROUND** → chuyển lĩnh vực tiếp theo.")
        b1,b2,b3,b4 = st.columns(4)
        db = require_db()
        if b1.button("SET PITCHING", use_container_width=True):
            db.table("round_state").update({"current_category": selected_cat,"status":"PITCHING","updated_at":datetime.now(timezone.utc).isoformat()}).eq("server_id",server_id).execute()
            log_event(server_id,"TEACHER","SET_PITCHING",{"category":selected_cat}); st.rerun()
        if b2.button("OPEN INVESTMENT", type="primary", use_container_width=True):
            db.table("round_state").update({"current_category": selected_cat,"status":"OPEN","updated_at":datetime.now(timezone.utc).isoformat()}).eq("server_id",server_id).execute()
            log_event(server_id,"TEACHER","OPEN_ROUND",{"category":selected_cat}); st.rerun()
        if b3.button("CLOSE ROUND", use_container_width=True):
            db.table("round_state").update({"current_category": selected_cat,"status":"CLOSED","updated_at":datetime.now(timezone.utc).isoformat()}).eq("server_id",server_id).execute()
            log_event(server_id,"TEACHER","CLOSE_ROUND",{"category":selected_cat}); st.rerun()
        if b4.button("FINISH ALL", use_container_width=True):
            db.table("round_state").update({"status":"FINISHED","updated_at":datetime.now(timezone.utc).isoformat()}).eq("server_id",server_id).execute()
            log_event(server_id,"TEACHER","FINISH_ALL",{}); st.rerun()

        st.divider()
        st.markdown("### Thứ tự pitching trong lĩnh vực")
        cat_projects = sorted([p for p in projects if p["category"] == selected_cat], key=lambda p: project_sort_key(server_id, p))
        if cat_projects:
            st.dataframe(pd.DataFrame(cat_projects)[["project_code","project_name","one_liner"]], hide_index=True, use_container_width=True)
        else:
            st.info("Chưa có dự án cho lĩnh vực này.")

        st.divider()
        st.markdown("### Tải dữ liệu sau mỗi vòng đầu tư")
        closed_events = q("audit_logs", "action,details", server_id=server_id)
        closed_categories = {
            event.get("details", {}).get("category")
            for event in closed_events
            if event.get("action") == "CLOSE_ROUND" and isinstance(event.get("details"), dict)
        }
        is_current_closed = (
            selected_cat == round_state.get("current_category")
            and round_state.get("status") in ("CLOSED", "FINISHED")
        )
        has_closed_history = selected_cat in closed_categories
        currently_open = (
            selected_cat == round_state.get("current_category")
            and round_state.get("status") == "OPEN"
        )
        if currently_open:
            st.info("Vòng đang mở đầu tư. Đóng vòng trước khi tải dữ liệu.")
        elif is_current_closed or has_closed_history:
            details, totals = round_export_frames(server_id, selected_cat)
            st.caption("Dữ liệu được lấy mới từ Supabase khi tải; tệp chi tiết chỉ dành cho giảng viên vì chứa MSSV và họ tên.")
            if has_closed_history and not is_current_closed:
                st.caption("Đây là dữ liệu hiện tại của vòng đã đóng trước đó, không phải bản chụp lịch sử bất biến.")
            name = f"{server_id}_{selected_cat}"
            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    "⬇️ TẢI GIAO DỊCH (CSV)",
                    data=details.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{name}_giao_dich.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "⬇️ TẢI XẾP HẠNG (CSV)",
                    data=totals.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{name}_ket_qua.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            st.dataframe(totals, hide_index=True, use_container_width=True)
        else:
            st.info("Chưa ghi nhận thao tác CLOSE ROUND cho lĩnh vực này.")

    # MONITOR
    with tabs[2]:
        st.markdown("### 📺 Live investment monitor")
        live_results_panel(server_id)

    # RESULTS
    with tabs[3]:
        st.markdown("### Final results")
        pdf, idf = compute_results(server_id)
        if pdf.empty:
            st.info("Chưa có dự án.")
        else:
            st.markdown("#### Most-funded project in each category")
            winners = []
            for cat in CATEGORIES:
                sub = pdf[pdf["Category"] == cat].sort_values("Funding", ascending=False)
                if not sub.empty:
                    top = sub.iloc[0]
                    winners.append({
                        "Category": CATEGORY_LABELS[cat], "Project": top["Project"],
                        "Funding": format_money(top["Funding"]), "Investors": int(top["Investors"])
                    })
            st.dataframe(pd.DataFrame(winners), hide_index=True, use_container_width=True)

            st.divider()
            st.markdown("#### Enter final project scores")
            st.caption("Top 5 Investors được tính chỉ từ Investment Quality = weighted average của Final Project Score theo số vốn đã đầu tư.")
            for p in projects:
                c1,c2,c3 = st.columns([1.5,.8,.5])
                with c1: st.write(f"**{p['project_code']} · {p['project_name']}**")
                with c2:
                    score = st.number_input("Score", min_value=0.0, max_value=100.0, value=float(p.get("final_score") or 0), step=.5, key=f"score_{p['id']}", label_visibility="collapsed")
                with c3:
                    if st.button("SAVE", key=f"scoresave_{p['id']}"):
                        require_db().table("projects").update({"final_score":score}).eq("id",p["id"]).execute()
                        st.success("Saved")
                        st.rerun()

            pdf, idf = compute_results(server_id)
            ranked = idf.dropna(subset=["Investment Quality"]).sort_values("Investment Quality", ascending=False).head(5).copy()
            if not ranked.empty:
                ranked.insert(0, "Rank", range(1, len(ranked)+1))
                ranked["Investment Quality"] = ranked["Investment Quality"].round(2)
                ranked["Invested"] = ranked["Invested"].apply(format_money)
                st.markdown("#### Top 5 Investors")
                st.dataframe(ranked[["Rank","Student","Student ID","Investment Quality","Invested"]], hide_index=True, use_container_width=True)
            else:
                st.info("Nhập Final Score cho các dự án để tính Top 5 Investors.")

            st.divider()
            st.markdown("#### Project result detail")
            detail = pdf.copy()
            detail["Funding"] = detail["Funding"].apply(format_money)
            st.dataframe(detail.drop(columns=["id"]), hide_index=True, use_container_width=True)

    # INTEGRITY
    with tabs[4]:
        st.markdown("### Integrity / reciprocal investment")
        flags = reciprocal_flags(server_id)
        if flags:
            st.warning("Phát hiện các cặp nhóm có dòng vốn hai chiều. Teacher nên xem xét trước khi công bố kết quả.")
            st.dataframe(pd.DataFrame(flags), hide_index=True, use_container_width=True)
        else:
            st.success("Chưa phát hiện reciprocal investment hai chiều ở cấp nhóm.")
        st.caption("MVP chỉ cảnh báo; không tự động vô hiệu hóa để tránh false positive. Có thể bổ sung nút invalidate/review ở phiên bản tiếp theo.")


# =========================
# ROUTER
# =========================
if "role" not in st.session_state:
    login_screen()
elif st.session_state.role == "student":
    student_app()
elif st.session_state.role == "teacher":
    teacher_app()
else:
    login_screen()
