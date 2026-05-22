import streamlit as st
import datetime
import csv
import io
import pandas as pd

# Import modular custom logic engines
import database as db
import auth

st.set_page_config(layout="wide")

# Inject hidden HTML link descriptors to guide mobile devices to your static manifest configuration mapping
st.components.v1.html(
    """
    <head>
        <link rel="manifest" href="app/static/manifest.json">
        <meta name="theme-color" content="#ff4b4b">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
    </head>
    """,
    height=0,
    width=0
)

# Initialize Session State Variables
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "family_id" not in st.session_state: st.session_state.family_id = None
if "auth_email" not in st.session_state: st.session_state.auth_email = None
if "otp_sent" not in st.session_state: st.session_state.otp_sent = False
if "login_mode" not in st.session_state: st.session_state.login_mode = "email"
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "admin_password_mode" not in st.session_state: st.session_state.admin_password_mode = False
if "register_mode" not in st.session_state: st.session_state.register_mode = False


def logout():
    st.session_state.logged_in = False
    st.session_state.family_id = None
    st.session_state.auth_email = None
    st.session_state.otp_sent = False
    st.session_state.login_mode = "email"
    st.session_state.is_admin = False
    st.session_state.admin_password_mode = False
    st.session_state.register_mode = False
    st.rerun()


# Create a master visual container context to prevent interface leaks
main_display_viewport = st.container()

# -------------------------------------------------------------
# 1. IDENTITY AUTHENTICATION ENGINE (ISOLATED EXECUTION LAYER)
# -------------------------------------------------------------
if not st.session_state.logged_in:
    with main_display_viewport:
        st.title("Yogakshemasabha Portal")

        # ---- SUB-ROUTE: NEW HOUSEHOLD REGISTRATION FORM ----
        if st.session_state.register_mode:
            st.subheader("📝 Request New Household Registration")
            st.caption(
                "Fill out your family profile details. This request will be sent to the managing committee for approval before access is granted.")

            with st.form("new_family_reg_form"):
                reg_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name) *")
                reg_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name) *")
                reg_goth = st.text_input("ഗോത്രം (Gothram)")
                reg_email = st.text_input("Login Email ID (This will be your username) *").strip().lower()
                reg_phone = st.text_input("Contact Phone Number *")
                reg_dob = st.date_input("Head of Family DOB *", value=datetime.date(1985, 1, 1),
                                        min_value=datetime.date(1920, 1, 1), max_value=datetime.date.today())
                reg_addr = st.text_area("മേൽവിലാസം (Master Address) *")

                if st.form_submit_button("Submit Registration Request"):
                    if not reg_head or not reg_illam or not reg_email or not reg_phone or not reg_addr:
                        st.error("❌ Please fill in all fields marked with *")
                    elif "@" not in reg_email or "." not in reg_email:
                        st.error("❌ Invalid Email format layout structure.")
                    elif db.check_family_email_exists(reg_email):
                        st.error("🛑 This email is already linked to an existing registered profile.")
                    else:
                        registration_payload = {
                            "head_of_family": reg_head.strip(),
                            "illam_name": reg_illam.strip(),
                            "gothram": reg_goth.strip(),
                            "email_id": reg_email.strip(),
                            "address": reg_addr.strip(),
                            "head_phone": reg_phone.strip(),
                            "head_dob": reg_dob.strftime("%Y-%m-%d")
                        }
                        db.submit_new_family_registration(reg_email, registration_payload)
                        st.success(
                            "📩 Request sent successfully! The committee will review and activate your access portal shortly.")
                        st.session_state.register_mode = False
                        st.rerun()

            if st.button("← Back to Login"):
                st.session_state.register_mode = False
                st.rerun()

        # ---- DEFAULT LOG IN ENTRY ROUTE ----
        elif st.session_state.login_mode == "email":
            st.subheader("Household Email / Admin Login")
            admin_cfg = db.fetch_admin_config()
            admin_user_target = admin_cfg["username"]

            if not st.session_state.otp_sent and not st.session_state.admin_password_mode:
                input_email = st.text_input("Enter Email Identifier / Admin Username").strip().lower()

                if st.button("Proceed to Login"):
                    if input_email == admin_user_target:
                        st.session_state.auth_email = input_email
                        st.session_state.admin_password_mode = True
                        st.rerun()
                    elif "@" not in input_email or "." not in input_email:
                        st.error("Please enter a valid email address.")
                    else:
                        if db.check_family_email_exists(input_email):
                            try:
                                db.send_supabase_otp(input_email)
                                st.session_state.auth_email = input_email
                                st.session_state.otp_sent = True
                                st.success(f"Verification code sent to {input_email}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Auth System Error: {str(e)}")
                        else:
                            st.error("Email identifier not found in records. Use Onboarding route below if first time.")

                st.write("---")
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Forgot / No Email ID Registered? Click here to verify via Family Details"):
                        st.session_state.login_mode = "backdoor"
                        st.rerun()
                with col_b2:
                    if st.button("✨ New Family? Register Household Profile Here"):
                        st.session_state.register_mode = True
                        st.rerun()

            # ADMIN GATEWAY PASSWORD PROMPT
            elif st.session_state.admin_password_mode:
                st.info(f"🔑 Administrator Portal Access: **{st.session_state.auth_email}**")
                admin_pwd_input = st.text_input("Enter Admin Management Password", type="password")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Verify & Open Workspace"):
                        if admin_pwd_input == admin_cfg["password"]:
                            st.session_state.is_admin = True
                            st.session_state.logged_in = True
                            st.rerun()
                        else:
                            st.error("Invalid Administrative Password Credential.")
                with col2:
                    if st.button("← Cancel"):
                        st.session_state.admin_password_mode = False
                        st.session_state.auth_email = None
                        st.rerun()

            # STANDARD USER OTP PROMPT
            elif st.session_state.otp_sent:
                st.info(f"Logging in as: **{st.session_state.auth_email}**")
                otp_token = st.text_input("Enter 6-Digit Code", max_chars=6).strip()
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Verify & Login"):
                        family_lookup = db.fetch_family_by_email(st.session_state.auth_email)
                        if family_lookup:
                            st.session_state.family_id = family_lookup["family_id"]
                            st.session_state.logged_in = True
                            st.rerun()
                with col2:
                    if st.button("← Cancel"):
                        st.session_state.otp_sent = False
                        st.rerun()

        elif st.session_state.login_mode == "backdoor":
            st.subheader("Verify via Household Details (Onboarding)")
            input_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)").strip()
            input_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)").strip()
            if st.button("Verify & Open Profile"):
                records = db.verify_backdoor_details(input_head, input_illam)
                if records:
                    found = records[0]
                    if found.get("email_id") and str(found.get("email_id")).strip() != "" and str(
                            found.get("email_id")).lower() != "none":
                        st.error(
                            f"🛑 Access Restricted! This profile already has a registered email ({found['email_id']}). You must log in via the regular Email screen.")
                    else:
                        st.session_state.family_id = found["family_id"]
                        st.session_state.logged_in = True
                        st.rerun()
                else:
                    st.error("Authentication Failed. No matching records found.")
            if st.button("← Back to Email Login"):
                st.session_state.login_mode = "email"
                st.rerun()

# -------------------------------------------------------------
# 2. THE MASTER CONTROL PANEL (ADMINISTRATION PORTAL)
# -------------------------------------------------------------
elif st.session_state.is_admin:
    st.sidebar.title("🛡️ Admin Workspace")
    if st.sidebar.button("Secure Log Out"): logout()

    with main_display_viewport:
        st.subheader("📊 Community Directory Analytics")
        with st.expander("👁️ Open Metrics & Demographic Charts", expanded=False):
            with st.spinner("Compiling visual intelligence statistics..."):
                all_m_stats = db.fetch_all_members_global()
                if all_m_stats:
                    stats_df = pd.DataFrame(all_m_stats)
                    stat_col1, stat_col2 = st.columns(2)
                    with stat_col1:
                        st.markdown("**🩸 Blood Group Distribution Matrix**")
                        if "blood_group" in stats_df.columns:
                            blood_counts = stats_df["blood_group"].fillna("Not Identified").value_counts()
                            st.bar_chart(blood_counts, horizontal=True, color="#ff4b4b")
                    with stat_col2:
                        st.markdown("**🎂 Family Relationship Metrics**")
                        if "relation" in stats_df.columns:
                            relation_counts = stats_df["relation"].fillna("Head/Other").value_counts()
                            st.bar_chart(relation_counts, color="#0068c9")
        st.write("---")

        admin_tab = st.tabs(["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "🎂 Age Verification Filter",
                             "⚙️ Admin Settings"])

        # ---- TAB 1: MODIFIED TABLE-BASED AUDIT PIPELINE QUEUE ----
        with admin_tab[0]:
            st.header("Modifications Awaiting Administrative Clearance")
            st.subheader("💳 Staged Subscription Confirmations")
            all_households = db.fetch_all_families_global()
            payment_requests = [x for x in all_households if x.get("verification_status") == "Payment Submitted"]

            if not payment_requests:
                st.info("No incoming payment confirmations awaiting verification.")
            else:
                for p_req in payment_requests:
                    with st.container(border=True):
                        st.write(f"🏡 **{p_req['head_of_family']}** | ഇല്ലം: {p_req['illam_name']}")
                        st.write(f"Reference Token Code: `{p_req['payment_reference']}`")
                        pay_c1, pay_c2 = st.columns(2)
                        with pay_c1:
                            if st.button("✅ Verify Payment & Issue Receipt", key=f"pay_app_{p_req['family_id']}"):
                                db.update_family_verification_state(p_req['family_id'], "Approved")
                                st.success("Payment verified! Digital membership receipt issued live.")
                                st.rerun()
                        with pay_c2:
                            if p_req.get("payment_reference"):
                                if st.button("❌ Reject / Flag Payment Log", key=f"pay_rej_{p_req['family_id']}"):
                                    db.update_family_verification_state(p_req['family_id'], "Pending Update")
                                    st.warning("Payment log rejected and profile unlocked.")
                                    st.rerun()
            st.write("---")

            st.subheader("📝 Pending Profile Core Alterations")
            pending_data = db.fetch_pending_approvals()
            if not pending_data:
                st.success("🎉 All clear! The pending approval tracking queue is empty.")
            else:
                for req in pending_data:
                    req_id = req["approval_id"]
                    table = req["target_table"]
                    action = req["action_type"]
                    payload = req["change_payload"] or {}
                    target_row_id = req["target_id"]

                    with st.container(border=True):
                        st.markdown(f"#### ✉️ Request #{req_id}: **{action}** on **{table.upper()}**")
                        st.caption(f"Submitted by: `{req['requested_by']}` | Target ID Reference: `{target_row_id}`")

                        # Dataframe Layout Strategy Implementation
                        if action == "INSERT":
                            st.info("🆕 Complete New Entry Profile Dataset:")
                            df_parsed = pd.DataFrame([payload])
                            st.dataframe(df_parsed, use_container_width=True, hide_index=True)

                        elif action == "DELETE":
                            st.warning("⚠️ Target Record Profile Slated for Deletion:")
                            df_parsed = pd.DataFrame([payload])
                            st.dataframe(df_parsed, use_container_width=True, hide_index=True)

                        elif action == "UPDATE":
                            st.info("🔄 Modified Structural Fields Matrix View:")
                            diff_summary = []
                            if table == "members" and target_row_id:
                                try:
                                    old_res = db.supabase.table("members").select("*").eq("member_id",
                                                                                          target_row_id).execute()
                                    if old_res.data:
                                        old_record = old_res.data[0]
                                        for k, new_v in payload.items():
                                            old_v = old_record.get(k)
                                            if str(old_v).strip() != str(new_v).strip():
                                                diff_summary.append({"Field Param": k, "Prior Stored Value": str(old_v),
                                                                     "New Requested Value": str(new_v)})
                                except:
                                    pass

                            if not diff_summary:
                                for k, new_v in payload.items():
                                    diff_summary.append({"Field Param": k, "Prior Stored Value": "N/A",
                                                         "New Requested Value": str(new_v)})

                            st.table(pd.DataFrame(diff_summary))

                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("👍 Approve Change", key=f"appr_{req_id}"):
                                db.process_approval_action(req_id, action, table, payload, target_row_id)
                                st.success("Modification pushed live and user notified!")
                                st.rerun()
                        with c2:
                            if st.button("👎 Reject & Drop", key=f"rej_{req_id}"):
                                db.reject_pending_approval(req_id)
                                st.warning("Change discarded and user notified.")
                                st.rerun()

        # ---- TAB 2: OPTIMIZED DIRECTORY MATRIX ----
        with admin_tab[1]:
            st.header("Global Directory Master Tracking View")
            search_q = st.text_input("Type here to search across Head Name, Illam, or Address (Press Enter)").strip()
            display_fams = db.fetch_recent_families_global(limit=10) if search_q == "" else db.search_families_global(
                search_q)

            if not display_fams:
                st.info("No matching records found.")
            else:
                for f in display_fams:
                    if f["family_id"] == 999999: continue
                    with st.expander(f"🏡 {f.get('head_of_family')} | ഇല്ലം: {f.get('illam_name')}"):
                        if not f.get("email_id"):
                            pre_reg_email = st.text_input("Enter Email to bind to this profile",
                                                          key=f"pr_em_txt_{f['family_id']}").strip().lower()
                            if st.button("🔗 Direct Pre-Register & Bind Email", key=f"pr_em_btn_{f['family_id']}"):
                                if "@" not in pre_reg_email or "." not in pre_reg_email:
                                    st.error("Invalid email pattern structure.")
                                else:
                                    db.link_family_email(f['family_id'], pre_reg_email)
                                    st.success("Email bound successfully!")
                                    st.rerun()
                        else:
                            st.info(f"Registered Login Identifier: **{f['email_id']}**")
                            if st.button("🔄 Reset Linked Email / Open Backdoor", key=f"rst_{f['family_id']}"):
                                db.link_family_email(f['family_id'], None)
                                st.success("Login identity reset completed.")
                                st.rerun()

                        st.write("---")
                        with st.form(f"adm_fam_form_{f['family_id']}"):
                            st.subheader("🛠️ Override Household Header")
                            a_head = st.text_input("Head Name", value=f["head_of_family"])
                            a_illam = st.text_input("Illam Name", value=f["illam_name"])
                            a_goth = st.text_input("Gothram", value=f.get("gothram", ""))
                            a_addr = st.text_area("Master Address", value=f["address"])

                            b_cols = st.columns([4, 1])
                            with b_cols[0]:
                                # FIXED: Converted from custom variable prefix call to native Streamlit namespace
                                if st.form_submit_button("💾 Direct Save Header Changes"):
                                    db.update_family_header(f['family_id'], a_head, a_illam, a_goth, a_addr)
                                    st.success("Header saved directly!")
                                    st.rerun()
                            with b_cols[1]:
                                # FIXED: Converted from custom variable prefix call to native Streamlit namespace
                                if st.form_submit_button("❌ Drop Household"):
                                    db.admin_direct_delete_family(f['family_id'])
                                    st.warning("Household entry dropped!")
                                    st.rerun()

                        st.write("---")
                        st.subheader("🛠️ Override Family Members Registry")
                        m_records = db.fetch_family_members(f['family_id'])
                        for m in m_records:
                            with st.container(border=True):
                                with st.form(f"adm_mem_form_{m['member_id']}"):
                                    st.write(f"👤 **Member Data Record: {m['name']}**")
                                    ma_name = st.text_input("Name", value=m["name"])
                                    ma_rel = st.text_input("Relation", value=m["relation"])
                                    ma_dob = st.text_input("DOB (YYYY-MM-DD)",
                                                           value=str(m["dob"]) if m.get("dob") else "")
                                    ma_bg = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS,
                                                         index=auth.BLOOD_GROUPS.index(m["blood_group"]) if m.get(
                                                             "blood_group") in auth.BLOOD_GROUPS else 0)
                                    ma_phone = st.text_input("Phone", value=m.get("phone", ""))
                                    ma_email = st.text_input("Email", value=m.get("email", ""))
                                    ma_qual = st.text_input("Qualification", value=m.get("qualification", ""))
                                    ma_job = st.text_input("Job", value=m.get("job", ""))
                                    ma_adh = st.text_input("Aadhaar", value=m.get("adhaar", ""))
                                    ma_caddr = st.text_area("Current Address", value=m.get("current_address", ""))

                                    m_cols = st.columns([4, 1])
                                    with m_cols[0]:
                                        # FIXED: Converted to native Streamlit namespace
                                        if st.form_submit_button("💾 Save Member Direct"):
                                            is_valid, clean_a = auth.validate_aadhaar(ma_adh)
                                            if ma_name.strip() == "" or ma_rel.strip() == "" or ma_dob.strip() == "":
                                                st.error("Fields marked with * are mandatory parameters.")
                                            elif not is_valid:
                                                st.error("Invalid Aadhaar formatting.")
                                            else:
                                                db.admin_direct_save_member(m['member_id'], {
                                                    "name": ma_name.strip(), "relation": ma_rel.strip(),
                                                    "dob": ma_dob.strip(),
                                                    "blood_group": None if ma_bg == 'Not Identified' else ma_bg,
                                                    "phone": ma_phone.strip() if ma_phone else None,
                                                    "email": ma_email.strip() if ma_email else None,
                                                    "qualification": ma_qual.strip() if ma_qual else None,
                                                    "job": ma_job.strip() if ma_job else None,
                                                    "adhaar": clean_a if clean_a != "" else None,
                                                    "current_address": ma_caddr.strip()
                                                })
                                                st.success("Member saved!")
                                                st.rerun()
                                    with m_cols[1]:
                                        # FIXED: Converted to native Streamlit namespace
                                        if st.form_submit_button("❌ Drop"):
                                            db.admin_direct_delete_member(m['member_id'])
                                            st.warning("Member dropped!")
                                            st.rerun()

        # ---- TAB 3: REPORTS ENGINE ----
        with admin_tab[2]:
            st.header("Statutory Electoral & District Sabha Calculations")
            current_year = datetime.date.today().year
            st.subheader("1. Age Calculation Audit (18+)")
            target_date = st.date_input("Select Reference Cut-off Date", datetime.date.today(), key="voter_date_picker")

            if st.button("Calculate Voter Roll Registry (18+)"):
                with st.spinner("Executing lookup..."):
                    voters = auth.calculate_voter_roll(db.fetch_all_members_global(), db.fetch_all_families_global(),
                                                       target_date)
                if voters:
                    st.success(f"Found {len(voters)} members.")
                    st.dataframe(voters)
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=voters[0].keys())
                    writer.writeheader()
                    writer.writerows(voters)
                    st.download_button("📥 Download Voter Roll (CSV)", data=output.getvalue(),
                                       file_name=f"voter_roll_{target_date}.csv", mime="text/csv")

            st.write("---")
            st.subheader(f"2. District Sabha Yearly Registry ({current_year})")
            if st.button(f"Generate {current_year} District Sabha Report"):
                with st.spinner("Compiling report..."):
                    raw_members = db.fetch_district_sabha_report_data()
                    fam_map = {x["family_id"]: x for x in db.fetch_all_families_global()}
                    district_report = []
                    this_year_cutoff = datetime.date(current_year, 3, 31)
                    last_year_cutoff = datetime.date(current_year - 1, 3, 31)

                    for m in raw_members:
                        if not m.get("dob"): continue
                        try:
                            dob_parsed = datetime.datetime.strptime(str(m["dob"]), "%Y-%m-%d").date()
                            if (this_year_cutoff - dob_parsed).days / 365.25 < 18.0: continue
                            status = "New" if (last_year_cutoff - dob_parsed).days / 365.25 < 18.0 else "Existing"
                            f_info = fam_map.get(m["family_id"], {})
                            final_address = f_info.get("address", "N/A") if not m.get(
                                "current_address") or "Same as above" in m.get("current_address", "") else m.get(
                                "current_address")
                            district_report.append({"Name": m["name"], "DOB": m["dob"],
                                                    "Blood Group": m["blood_group"] or "Not Identified",
                                                    "Illam Name": f_info.get("illam_name", "N/A"),
                                                    "Address": final_address, "Phone": m["phone"] or "N/A",
                                                    "Status": status})
                        except:
                            pass
                if district_report:
                    st.success(f"Compiled {len(district_report)} entries.")
                    st.dataframe(district_report)
                    output_ds = io.StringIO()
                    writer_ds = csv.DictWriter(output_ds, fieldnames=district_report[0].keys())
                    writer_ds.writeheader()
                    writer_ds.writerows(district_report)
                    st.download_button(label="📥 Download District Sabha Report (CSV)", data=output_ds.getvalue(),
                                       file_name=f"district_sabha_report_march31_{current_year}.csv", mime="text/csv")

        # ---- TAB 4: SYSTEM CONFIGS ----
        with admin_tab[3]:
            st.header("Security Configuration Settings")
            current_config = db.fetch_admin_config()
            st.write("---")
            st.subheader("🗓️ Annual Institutional Renewal Lifecycle & Rates")
            verification_state = current_config.get("yearly_verification_active", False)

            with st.form("global_lifecycle_toggle_form"):
                toggle_switch = st.checkbox("Enable Global Yearly Audit & Subscription Window",
                                            value=verification_state)
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1: cfg_base = st.number_input("Base Family Fee (INR)",
                                                        value=float(current_config.get("base_family_fee", 700)),
                                                        step=50.0)
                with col_p2: cfg_thresh = st.number_input("Headcount Limit for Base Fee",
                                                          value=int(current_config.get("base_member_threshold", 4)),
                                                          step=1)
                with col_p3: cfg_add = st.number_input("Fee per Additional Member (INR)",
                                                       value=float(current_config.get("additional_member_fee", 100)),
                                                       step=10.0)
                if st.form_submit_button("Apply Global Changes"):
                    db.update_global_verification_toggle(toggle_switch, cfg_base, cfg_thresh, cfg_add)
                    st.success("🔒 Configuration variables updated live!")
                    st.rerun()

            st.write("---")
            st.subheader("💳 Configure Sabha Treasury UPI Parameters")
            with st.form("admin_upi_configuration_form"):
                new_upi_id = st.text_input("Sabha Official UPI ID / VPA Handle",
                                           value=current_config.get("upi_id", "sabha@upi")).strip()
                uploaded_qr = st.file_uploader("Upload Official UPI QR Code Image (PNG/JPG)",
                                               type=["png", "jpg", "jpeg"])
                if st.form_submit_button("Update Payment Assets"):
                    if new_upi_id == "":
                        st.error("UPI handle parameter cannot be empty.")
                    else:
                        db.update_admin_upi_credentials(new_upi_id, uploaded_qr.getvalue() if uploaded_qr else None)
                        st.success("🔒 Sabha treasury payment targets successfully modified live!")
                        st.rerun()

            st.write("---")
            with st.form("admin_settings_form"):
                st.subheader("🔑 Modify Core Access Credentials")
                new_username = st.text_input("Change Admin Username", value=current_config["username"]).strip()
                new_password = st.text_input("Set New Admin Password", type="password").strip()
                confirm_password = st.text_input("Confirm New Admin Password", type="password").strip()

                if st.form_submit_button("Update Access Credentials"):
                    if new_username == "" or new_password == "":
                        st.error("Fields cannot be blank.")
                    elif new_password != confirm_password:
                        st.error("❌ Password confirmation mismatch!")
                    else:
                        db.admin_update_credentials(new_username, new_password)
                        st.success("🔒 System credentials updated!")
                        st.rerun()

# -------------------------------------------------------------
# 3. STANDARD USER WORKSPACE (WITH AUTOMATED LOCKS & BANNERS)
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"): logout()

    admin_cfg = db.fetch_admin_config()
    is_audit_window = admin_cfg.get("yearly_verification_active", False)

    family_data = db.fetch_single_family(f_id)
    members_data = db.fetch_family_members(f_id)
    v_status = family_data.get("verification_status", "Pending Update")

    # Dynamic Pricing Calculations
    member_count = len(members_data) if members_data else 1
    db_base_fee = admin_cfg.get("base_family_fee", 700)
    db_threshold = admin_cfg.get("base_member_threshold", 4)
    db_add_fee = admin_cfg.get("additional_member_fee", 100)
    active_fee = int(db_base_fee) if member_count <= int(db_threshold) else int(db_base_fee) + (
                (member_count - int(db_threshold)) * int(db_add_fee))

    st.title("Yogakshemasabha Household Terminal")

    # Real-Time User Notification Center Banner Link
    notification_msg = family_data.get("admin_notification")
    if notification_msg:
        st.toast(notification_msg)
        with st.container(border=True):
            st.markdown(f"#### 🔔 Committee Feedback Alert")
            st.info(notification_msg)
            if st.button("Dismiss & Clear Notification"):
                db.clear_user_notification(f_id)
                st.rerun()

    # Dynamic Verification Queue Status Lock Checks
    is_stuck_in_approval_queue = db.check_if_user_has_pending_requests(st.session_state.auth_email)

    if is_stuck_in_approval_queue:
        st.error(
            "⏳ **Portal Locked:** Your recent profile modifications are currently sitting in the queue awaiting committee validation check-off. No further edits or payments can be submitted until an admin clears this ticket.")
        is_disabled = True
        is_payment_allowed = False
    else:
        # Automatic lifecycle un-binder: if admin processed the request, fields unlock immediately here!
        is_disabled = (v_status != "Pending Update")
        is_payment_allowed = (v_status == "Data Verified")

    if is_audit_window and not is_stuck_in_approval_queue:
        if v_status == "Pending Update":
            st.warning(
                f"📣 **Annual Verification Window is OPEN.** Household Strength: **{member_count} members** | Custom Dynamic Fee: **₹{active_fee}**")
            st.info(
                "👉 **Step 1:** Please review your household data parameters below, edit if necessary, and lock verification accuracy.")
        elif v_status == "Data Verified":
            st.success(
                "✅ Household profile verified! Please open the **💳 Settle Subscription** tab to complete payment.")
        elif v_status == "Payment Submitted":
            st.info("⏳ Reference token logged. Awaiting committee reconciliation check.")
        elif v_status == "Approved":
            st.balloons()
            st.success("🎉 Annual subscription approved! Download your printable receipt in the payment tab.")

    # BUILD MODULAR WORKSPACE TABS
    user_tabs = st.tabs(["🏡 Household Profile", "👥 Family Members Roster", "💳 Settle Subscription"])

    # ---- TAB 1: HOUSEHOLD IDENTITY CORE HEADER ----
    with user_tabs[0]:
        st.subheader("Household Structural Settings")
        if is_disabled or v_status != "Pending Update":
            if not is_stuck_in_approval_queue:
                st.info(
                    "🔒 Data has been locked for audit phase. If any corrections are needed, contact the Sabha Secretary.")
            st.markdown(f"**Head of Family Name:** {family_data.get('head_of_family')}")
            st.markdown(f"**Illam Name:** {family_data.get('illam_name')}")
            st.markdown(f"**Gothram:** {family_data.get('gothram')}")
            st.markdown(f"**Core Home Address:**")
            st.text(family_data.get('address', ''))
        else:
            with st.form("edit_family_header_modular_form"):
                h_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)",
                                       value=family_data.get('head_of_family', ''))
                h_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)", value=family_data.get('illam_name', ''))
                h_goth = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
                h_addr = st.text_area("മേൽവിലാസം (Address)", value=family_data.get('address', ''))
                if st.form_submit_button("💾 Save Household Information"):
                    db.update_family_header(f_id, h_head.strip(), h_illam.strip(), h_goth.strip(), h_addr.strip())
                    st.success("Master header variables updated successfully!")
                    st.rerun()

    # ---- TAB 2: FUNCTIONAL MEMBERS MANAGEMENT LAYER ----
    with user_tabs[1]:
        st.subheader("Manage Family Directory")
        header_address = family_data.get('address', '').strip()

        # ONE-CLICK BULK UPDATE FOR COMPLEX MEMBER ROSTERS
        with st.form("bulk_member_update_modular_form"):
            member_references = []

            if not members_data:
                st.info("ℹ️ No family members are currently mapped to this household profile.")
            else:
                for m in members_data:
                    m_id = m['member_id']
                    with st.container(border=True):
                        st.markdown(f"##### Profile Card: **{m['name']}** ({m['relation'] or 'Member'})")
                        c1, c2 = st.columns(2)
                        with c1:
                            m_name = st.text_input("Name *", value=m.get('name', ''), key=f"u_nm_{m_id}",
                                                   disabled=is_disabled)
                            m_rel = st.text_input("Relation *", value=m.get('relation', ''), key=f"u_rl_{m_id}",
                                                  disabled=is_disabled)
                            try:
                                parsed_dob = datetime.datetime.strptime(str(m.get('dob', '1990-01-01')),
                                                                        "%Y-%m-%d").date()
                            except:
                                parsed_dob = datetime.date(1990, 1, 1)
                            m_dob = st.date_input("DOB *", value=parsed_dob, min_value=datetime.date(1920, 1, 1),
                                                  max_value=datetime.date.today(), key=f"u_db_{m_id}",
                                                  disabled=is_disabled)
                            bg_idx = auth.BLOOD_GROUPS.index(m['blood_group']) if m.get(
                                'blood_group') in auth.BLOOD_GROUPS else 0
                            m_bg = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS, index=bg_idx,
                                                key=f"u_bg_{m_id}", disabled=is_disabled)
                        with c2:
                            m_phone = st.text_input("Phone Number",
                                                    value=str(m.get('phone', '')) if m.get('phone') else '',
                                                    key=f"u_ph_{m_id}", disabled=is_disabled)
                            m_email = st.text_input("Email", value=m.get('email', '') or '', key=f"u_em_{m_id}",
                                                    disabled=is_disabled)
                            m_qual = st.text_input("Qualification", value=m.get('qualification', '') or '',
                                                   key=f"u_ql_{m_id}", disabled=is_disabled)
                            m_job = st.text_input("Job / Occupation", value=m.get('job', '') or '', key=f"u_jb_{m_id}",
                                                  disabled=is_disabled)

                        m_adhaar = st.text_input("Aadhaar Number (12 numeric digits)",
                                                 value=str(m.get('adhaar', '')) if m.get('adhaar') else '',
                                                 key=f"u_ad_{m_id}", disabled=is_disabled)
                        is_same_initial = (
                                    m.get('current_address', '').strip() == header_address or m.get('current_address',
                                                                                                    '').strip() == "")
                        m_addr_sel = st.selectbox("Current Address Selection",
                                                  options=["Same as Household Address", "Custom Address"],
                                                  index=0 if is_same_initial else 1, key=f"u_rad_{m_id}",
                                                  disabled=is_disabled)
                        m_caddr = st.text_area("Enter Custom Current Address",
                                               value=m.get('current_address', '') if not is_same_initial else "",
                                               key=f"u_txa_{m_id}", disabled=is_disabled)

                        member_references.append(
                            {"member_id": m_id, "name": m_name, "relation": m_rel, "dob": m_dob, "blood_group": m_bg,
                             "phone": m_phone, "email": m_email, "qualification": m_qual, "job": m_job,
                             "adhaar": m_adhaar, "addr_sel": m_addr_sel, "custom_addr": m_caddr})

            st.write("")
            c_save1, c_save2 = st.columns([4, 1])
            with c_save1:
                submit_modifications = st.form_submit_button("💾 Save All Member Changes in One-Click",
                                                             disabled=is_disabled)
                if submit_modifications and member_references:
                    for r in member_references:
                        is_valid, clean_a = auth.validate_aadhaar(r["adhaar"])
                        if r["name"].strip() == "" or r["relation"].strip() == "":
                            st.error(f"❌ Mandatory values are blank on member card {r['name']}")
                        elif not is_valid:
                            st.error(f"❌ Invalid Aadhaar syntax on member card {r['name']}")
                        else:
                            final_m_addr = header_address if r["addr_sel"] == "Same as Household Address" else r[
                                "custom_addr"].strip()
                            db.submit_pending_approval("members", "UPDATE", st.session_state.auth_email, {
                                "name": r["name"].strip(), "relation": r["relation"].strip(),
                                "dob": r["dob"].strftime("%Y-%m-%d"),
                                "blood_group": None if r["blood_group"] == 'Not Identified' else r["blood_group"],
                                "phone": r["phone"].strip() if r["phone"] else None,
                                "email": r["email"].strip() if r["email"] else None,
                                "qualification": r["qualification"].strip() if r["qualification"] else None,
                                "job": r["job"].strip() if r["job"] else None,
                                "adhaar": clean_a if clean_a != "" else None, "current_address": final_m_addr
                            }, target_id=r["member_id"])
                    st.success("✨ Changes successfully queued for review!")
                    st.rerun()

            with c_save2:
                lock_profile = st.form_submit_button("🔒 Lock Verification", disabled=is_disabled)
                if lock_profile:
                    db.update_family_verification_state(f_id, "Data Verified")
                    st.success("Roster securely locked. Move to subscription payment tab next.")
                    st.rerun()

        # ADD / REMOVE BUTTON SECTIONS
        if not is_disabled:
            st.write("---")
            st.subheader("🛠️ Immediate Membership Operations Queue")

            for m in members_data:
                if st.button(f"❌ Request Deletion of {m['name']}", key=f"del_btn_{m['member_id']}"):
                    db.submit_pending_approval("members", "DELETE", st.session_state.auth_email, {"name": m['name']},
                                               target_id=m['member_id'])
                    st.warning(f"📩 Deletion review request generated for {m['name']}.")
                    st.rerun()

            with st.expander("➕ Request Adding a New Member to this Household"):
                n_name = st.text_input("Full Name *", key="n_name")
                n_rel = st.text_input("Relation *", key="n_rel")
                n_dob = st.date_input("DOB *", value=datetime.date(1995, 1, 1), min_value=datetime.date(1920, 1, 1),
                                      max_value=datetime.date.today(), key="n_dob")
                n_blood = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS, index=0, key="n_bg")
                n_phone = st.text_input("Phone Number", key="n_phone")
                n_email = st.text_input("Email Address", key="n_email")
                n_qual = st.text_input("Qualification", key="n_qual")
                n_job = st.text_input("Job / Profession", key="n_job")
                n_adhaar = st.text_input("Aadhaar Number", key="n_adhaar")
                n_addr_sel = st.radio("Current Address Context Selector",
                                      options=["Same as Household Address", "Custom Address"], index=0, key="n_rad")
                n_custom_addr = st.text_area("Enter Custom Current Address", value="",
                                             key="n_txa") if n_addr_sel == "Custom Address" else ""

                if st.button("Submit New Member Profile to Queue"):
                    if n_name.strip() == "" or n_rel.strip() == "":
                        st.error("❌ Mandatory parameters missing.")
                    else:
                        is_valid, clean_a = auth.validate_aadhaar(n_adhaar)
                        if not is_valid:
                            st.error("❌ Invalid Aadhaar template formatting.")
                        else:
                            final_n_addr = header_address if n_addr_sel == "Same as Household Address" else n_custom_addr.strip()
                            db.submit_pending_approval("members", "INSERT", st.session_state.auth_email, {
                                "family_id": f_id, "name": n_name.strip(), "relation": n_rel.strip(),
                                "dob": n_dob.strftime("%Y-%m-%d"),
                                "blood_group": None if n_blood == 'Not Identified' else n_blood,
                                "phone": n_phone.strip() if n_phone else None,
                                "email": n_email.strip() if n_email else None,
                                "qualification": n_qual.strip() if n_qual else None,
                                "job": n_job.strip() if n_job else None,
                                "adhaar": clean_a if clean_a != "" else None, "current_address": final_n_addr
                            })
                            st.success("📩 Insertion verification ticket safely staged in the admin queue!")
                            st.rerun()

    # ---- TAB 3: CHECKOUT GATEWAY ----
    with user_tabs[2]:
        if is_stuck_in_approval_queue:
            st.error(
                "⚠️ Payment engine locked. Your account features are frozen until your outstanding queue changes are reviewed by an administrator.")

        elif v_status == "Pending Update":
            st.info(
                "⚠️ Please complete your profile records updates and lock verification on **Tab 2 (Family Members Roster)** to unlock payment gateways.")

        elif v_status == "Data Verified":
            st.subheader("💳 Settle Annual Membership Dues")
            st.markdown(
                f"Please scan the QR tracking matrix below or wire your **`₹{active_fee}`** subscription directly to treasury.")

            pay_layout_col1, pay_layout_col2 = st.columns([1, 2])
            with pay_layout_col1:
                if admin_cfg.get("upi_qr_url"):
                    st.image(admin_cfg["upi_qr_url"], caption="Scan using GPay, PhonePe, or PayTM",
                             use_container_width=True)
                else:
                    st.warning("⚠️ UPI payment matrix chart graphic unavailable.")
            with pay_layout_col2:
                with st.container(border=True):
                    st.markdown("### 📋 Payment Instructions")
                    st.markdown(f"**Amount Due:** `₹{active_fee}`")
                    st.markdown(f"**Sabha VPA Address Handle:** `{admin_cfg.get('upi_id', 'sabha@upi')}`")
                    st.write("---")
                    with st.form("payment_submission_form"):
                        bank_ref_id = st.text_input("Enter 12-Digit Bank Transaction Reference Token ID *").strip()
                        if st.form_submit_button("Submit Reference ID"):
                            if bank_ref_id == "":
                                st.error("Reference trace index cannot be empty.")
                            else:
                                db.update_family_verification_state(f_id, "Payment Submitted", payment_ref=bank_ref_id)
                                st.success("Reference token safely pushed to treasury dashboard queue layout!")
                                st.rerun()

        elif v_status == "Payment Submitted":
            st.subheader("💳 Transaction Staged")
            st.info(
                f"Trace reference key `{family_data.get('payment_reference')}` is currently undergoing bank ledger validation checks. Your official central treasury receipt will drop here once validated.")

        elif v_status == "Approved":
            st.subheader("📥 Central Treasury Receipts Voucher")
            current_year = datetime.date.today().year
            receipt_template = f"""
====================================================
          YOGAKSHEMASABHA CENTRAL TREASURY
                OFFICIAL PAYMENT RECEIPT
====================================================
Receipt Date: {datetime.date.today().strftime('%d-%B-%Y')}
Household Unit: {family_data.get('head_of_family')}
Illam Name: {family_data.get('illam_name')}
Settlement Scope: Annual Verification Dues Term ({current_year})
Amount Paid: INR {active_fee}.00
Status: CLEAR / FULLY VERIFIED CORPS
----------------------------------------------------
Thank you for your active support towards the Sabha!
====================================================
"""
            st.code(receipt_template, language="text")
            st.download_button(label="📥 Download Printable Membership Receipt (TXT)", data=receipt_template,
                               file_name=f"sabha_receipt_{current_year}_{f_id}.txt", mime="text/plain")