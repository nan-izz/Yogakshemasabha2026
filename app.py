import streamlit as st
import datetime
import csv
import io

# Import modular custom logic engines
import database as db
import auth

st.set_page_config(layout="wide")

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
                reg_dob = st.text_input("Head of Family DOB * (YYYY-MM-DD)")
                reg_addr = st.text_area("മേൽവിലാസം (Master Address) *")

                if st.form_submit_button("Submit Registration Request"):
                    if not reg_head or not reg_illam or not reg_email or not reg_phone or not reg_dob or not reg_addr:
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
                            "head_dob": reg_dob.strip()
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

        # ---- ADMINISTRATIVE VISUAL ANALYTICS SHIELD ----
        st.subheader("📊 Community Directory Analytics")
        with st.expander("👁️ Open Metrics & Demographic Charts", expanded=False):
            with st.spinner("Compiling visual intelligence statistics..."):
                all_m_stats = db.fetch_all_members_global()

                if all_m_stats:
                    import pandas as pd

                    stats_df = pd.DataFrame(all_m_stats)

                    stat_col1, stat_col2 = st.columns(2)

                    with stat_col1:
                        st.markdown("**🩸 Blood Group Distribution Matrix**")
                        if "blood_group" in stats_df.columns:
                            blood_counts = stats_df["blood_group"].fillna("Not Identified").value_counts()
                            st.bar_chart(blood_counts, horizontal=True, color="#ff4b4b")
                        else:
                            st.info("No blood group parameters mapped.")

                    with stat_col2:
                        st.markdown("**🎂 Family Relationship Metrics**")
                        if "relation" in stats_df.columns:
                            relation_counts = stats_df["relation"].fillna("Head/Other").value_counts()
                            st.bar_chart(relation_counts, color="#0068c9")
                else:
                    st.info("Insufficient member records to compile layout graphs.")
        st.write("---")

        admin_tab = st.tabs(["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "🎂 Age Verification Filter",
                             "⚙️ Admin Settings"])

        # ---- TAB 1: PENDING USER CLEARANCE QUEUE & PAYMENTS ----
        with admin_tab[0]:
            st.header("Modifications Awaiting Administrative Clearance")

            # --- SUB-SECTION: SUBSCRIPTION LEDGER VERIFICATIONS ---
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

            # --- DEFAULT CORE PROFILE UPDATES QUEUE ---
            st.subheader("📝 Pending Profile Core Alterations")
            pending_data = db.fetch_pending_approvals()
            if not pending_data:
                st.success("🎉 All clear! The pending approval tracking queue is empty.")
            else:
                for req in pending_data:
                    req_id, table, action, payload = req["approval_id"], req["target_table"], req["action_type"], (
                                req["change_payload"] or {})
                    with st.container(border=True):
                        st.subheader(f"Request #{req_id}: {action} on {table.upper()}")
                        st.caption(f"Submitted by: {req['requested_by']} | Row Key: {req['target_id']}")
                        st.json(payload)

                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("👍 Approve Change", key=f"appr_{req_id}"):
                                db.process_approval_action(req_id, action, table, payload, req["target_id"])
                                st.success("Modification pushed live!")
                                st.rerun()
                        with c2:
                            if st.button("👎 Reject & Drop", key=f"rej_{req_id}"):
                                db.reject_pending_approval(req_id)
                                st.warning("Change discarded.")
                                st.rerun()

        # ---- TAB 2: OPTIMIZED DIRECTORY MATRIX ----
        with admin_tab[1]:
            st.header("Global Directory Master Tracking View")
            search_q = st.text_input("Type here to search across Head Name, Illam, or Address (Press Enter)").strip()

            if search_q == "":
                st.subheader("Latest Updated 10 Households")
                display_fams = db.fetch_recent_families_global(limit=10)
            else:
                st.subheader(f"Search Results for: '{search_q}'")
                display_fams = db.search_families_global(search_q)

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
                                if st.form_submit_button("💾 Direct Save Header Changes"):
                                    db.update_family_header(f['family_id'], a_head, a_illam, a_goth, a_addr)
                                    st.success("Header saved directly!")
                                    st.rerun()
                            with b_cols[1]:
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
                                        if st.form_submit_button("❌ Drop"):
                                            db.admin_direct_delete_member(m['member_id'])
                                            st.warning("Member dropped!")
                                            st.rerun()

        # ---- TAB 3: AGE VERIFICATION & DISTRICT SABHA ANNUAL REPORTS ----
        with admin_tab[2]:
            st.header("Statutory Electoral & District Sabha Calculations")
            current_year = datetime.date.today().year

            # --- SUB SECTION 1: VOTER ROLL REGISTRY ---
            st.subheader("1. Age Calculation Audit (18+)")
            target_date = st.date_input("Select Reference Cut-off Date", datetime.date.today(), key="voter_date_picker")

            if st.button("Calculate Voter Roll Registry (18+)"):
                with st.spinner("Executing dynamic lookup step..."):
                    all_members = db.fetch_all_members_global()
                    all_fams_voter = db.fetch_all_families_global()
                    voters = auth.calculate_voter_roll(all_members, all_fams_voter, target_date)

                if voters:
                    st.success(f"Found {len(voters)} members who match eligibility rules on {target_date}")
                    st.dataframe(voters)

                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=voters[0].keys())
                    writer.writeheader()
                    writer.writerows(voters)
                    st.download_button("📥 Download Voter Roll Registry (CSV)", data=output.getvalue(),
                                       file_name=f"voter_roll_{target_date}.csv", mime="text/csv")
                else:
                    st.info("No members match criteria constraints for this date parameters.")

            st.write("---")

            # --- SUB SECTION 2: DISTRICT SABHA ANNUAL EXPORT (AS OF MARCH 31st) ---
            st.subheader(f"2. District Sabha Yearly Registry ({current_year})")
            st.caption(f"Generates the annual report with ages calculated strictly as of **March 31, {current_year}**.")

            if st.button(f"Generate {current_year} District Sabha Report"):
                with st.spinner("Compiling metrics based on March 31st constraints..."):
                    raw_members = db.fetch_district_sabha_report_data()
                    all_fams_sabha = db.fetch_all_families_global()

                    fam_map = {x["family_id"]: x for x in all_fams_sabha}
                    district_report = []

                    this_year_cutoff = datetime.date(current_year, 3, 31)
                    last_year_cutoff = datetime.date(current_year - 1, 3, 31)

                    for m in raw_members:
                        if not m.get("dob"):
                            continue

                        try:
                            dob_parsed = datetime.datetime.strptime(str(m["dob"]), "%Y-%m-%d").date()

                            age_this_year = (this_year_cutoff - dob_parsed).days / 365.25
                            age_last_year = (last_year_cutoff - dob_parsed).days / 365.25

                            if age_this_year < 18.0:
                                continue

                            if age_last_year < 18.0:
                                status = "New"
                            else:
                                status = "Existing"

                            f_info = fam_map.get(m["family_id"], {})

                            final_address = m.get("current_address")
                            if not final_address or "Same as above" in final_address:
                                final_address = f_info.get("address", "N/A")

                            district_report.append({
                                "Name": m["name"],
                                "DOB": m["dob"],
                                "Blood Group": m["blood_group"] or "Not Identified",
                                "Illam Name": f_info.get("illam_name", "N/A"),
                                "Address": final_address,
                                "Phone": m["phone"] or "N/A",
                                "Status": status
                            })
                        except:
                            pass

                if district_report:
                    st.success(
                        f"Successfully compiled {len(district_report)} member rows active as of March 31, {current_year}!")
                    st.dataframe(district_report)

                    output_ds = io.StringIO()
                    writer_ds = csv.DictWriter(output_ds, fieldnames=district_report[0].keys())
                    writer_ds.writeheader()
                    writer_ds.writerows(district_report)

                    st.download_button(
                        label=f"📥 Download District Sabha Registry (As of March 31, {current_year}).csv",
                        data=output_ds.getvalue(),
                        file_name=f"district_sabha_report_march31_{current_year}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning(f"No member entries met the 18+ eligibility rules on March 31, {current_year}.")

        # ---- TAB 4: ADMIN SETTINGS (LIFECYCLE & RATES MANAGEMENT) ----
        with admin_tab[3]:
            st.header("Security Configuration Settings")
            current_config = db.fetch_admin_config()

            # --- RENEWAL TOGGLE & CONFIGURABLE FORMULA CONTROLS ---
            st.write("---")
            st.subheader("🗓️ Annual Institutional Renewal Lifecycle & Rates")
            verification_state = current_config.get("yearly_verification_active", False)
            c_base_fee = current_config.get("base_family_fee", 700)
            c_threshold = current_config.get("base_member_threshold", 4)
            c_add_fee = current_config.get("additional_member_fee", 100)

            with st.form("global_lifecycle_toggle_form"):
                toggle_switch = st.checkbox("Enable Global Yearly Audit & Subscription Window",
                                            value=verification_state)

                st.markdown("##### 🪙 Dynamic Subscription Fee Formula Setup")
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1:
                    cfg_base = st.number_input("Base Family Fee (INR)", value=float(c_base_fee), step=50.0)
                with col_p2:
                    cfg_thresh = st.number_input("Member Headcount Limit for Base Fee", value=int(c_threshold), step=1)
                with col_p3:
                    cfg_add = st.number_input("Fee per Additional Member (INR)", value=float(c_add_fee), step=10.0)

                st.caption("💡 Formula: Base Fee + (Max(0, Total Members - Headcount Limit) × Additional Fee)")

                if st.form_submit_button("Apply Global Lifecycle & Rate Changes"):
                    db.update_global_verification_toggle(toggle_switch, cfg_base, cfg_thresh, cfg_add)
                    st.success("🔒 System-wide renewal criteria and rate variables updated live!")
                    st.rerun()

            # --- DYNAMIC UPI & QR CODE INTERFACE MANAGEMENT ---
            st.write("---")
            st.subheader("💳 Configure Sabha Treasury UPI Parameters")
            current_upi_id = current_config.get("upi_id", "sabha@upi")
            current_qr_url = current_config.get("upi_qr_url", None)

            with st.form("admin_upi_configuration_form"):
                new_upi_id = st.text_input("Sabha Official UPI ID / VPA Handle", value=current_upi_id).strip()
                uploaded_qr = st.file_uploader("Upload Official UPI QR Code Image (PNG/JPG)",
                                               type=["png", "jpg", "jpeg"])

                if current_qr_url:
                    st.info("💡 An active QR Code scan chart image is currently stored in production.")

                if st.form_submit_button("Update Payment Gateway Assets"):
                    if new_upi_id == "":
                        st.error("UPI handle parameter cannot be empty.")
                    else:
                        file_bytes = uploaded_qr.getvalue() if uploaded_qr is not None else None
                        db.update_admin_upi_credentials(new_upi_id, file_bytes)
                        st.success("🔒 Sabha treasury payment targets successfully modified live!")
                        st.rerun()

            st.write("---")
            # --- ROOT PASSWORD ENGINE UPDATE ---
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
# 3. STANDARD USER PROFILE DASHBOARD (RENEWAL & CYCLE ENABLED)
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"): logout()

    # Read live variables from config matrix
    admin_cfg = db.fetch_admin_config()
    is_audit_window = admin_cfg.get("yearly_verification_active", False)

    family_data = db.fetch_single_family(f_id)
    members_data = db.fetch_family_members(f_id)
    v_status = family_data.get("verification_status", "Pending Update")

    # --- DYNAMIC CONFIGURABLE HEADCOUNT PRICING MATH ENGINE ---
    member_count = len(members_data) if members_data else 1
    db_base_fee = admin_cfg.get("base_family_fee", 700)
    db_threshold = admin_cfg.get("base_member_threshold", 4)
    db_add_fee = admin_cfg.get("additional_member_fee", 100)

    if member_count <= int(db_threshold):
        active_fee = int(db_base_fee)
    else:
        active_fee = int(db_base_fee) + ((member_count - int(db_threshold)) * int(db_add_fee))

    st.title("Yogakshemasabha Household Terminal")

    # --- SUBSCRIPTION ALERT ENGINE BANNER LINK ---
    if is_audit_window:
        st.warning(
            f"📣 **Annual Verification Window is OPEN.** Household Strength: **{member_count} members** | Custom Dynamic Fee: **₹{active_fee}**")
        if v_status == "Pending Update":
            st.info(
                "👉 **Step 1:** Please review your household data parameters below, edit if necessary, and lock verification accuracy.")
        elif v_status == "Data Verified":
            st.success(
                "✅ **Step 2:** Data records locked and verified! Proceed to the secure UPI checkout block below.")
        elif v_status == "Payment Submitted":
            st.info(
                "⏳ **Step 3:** Payment trace reference submitted to treasury log. Awaiting committee validation confirmation.")
        elif v_status == "Approved":
            st.balloons()
            st.success(
                "🎉 **Completed:** Annual membership subscription validated! Your digital treasury voucher is available underneath.")

    if "form_edit_enabled" not in st.session_state:
        st.session_state.form_edit_enabled = False

    # --- ACTION WRAPPER A: ONE-CLICK SAVE INTEGRATED PROFILE CONTROLS ---
    if v_status == "Pending Update":
        col_ctrl1, col_ctrl2 = st.columns([5, 1])
        with col_ctrl2:
            if not st.session_state.form_edit_enabled:
                if st.button("✏️ Edit Fields"):
                    st.session_state.form_edit_enabled = True
                    st.rerun()
            else:
                if st.button("🔒 Cancel Edit"):
                    st.session_state.form_edit_enabled = False
                    st.rerun()

        with st.form("master_unified_household_form"):
            st.header("🏡 Master Household Identity")
            is_disabled = not st.session_state.form_edit_enabled

            f_head = st.text_input("Head of Family Name", value=family_data.get('head_of_family', ''),
                                   disabled=is_disabled)
            f_illam = st.text_input("Illam Name", value=family_data.get('illam_name', ''), disabled=is_disabled)
            f_goth = st.text_input("Gothram", value=family_data.get('gothram', ''), disabled=is_disabled)
            f_addr = st.text_area("Master Core Address", value=family_data.get('address', ''), disabled=is_disabled)

            st.write("---")
            st.header("👥 Household Members Roster")
            member_input_references = []

            for m in members_data:
                m_id = m['member_id']
                st.markdown(f"##### Member Data Record: **{m['name']}** ({m['relation']})")

                c1, c2, c3 = st.columns(3)
                with c1:
                    m_name = st.text_input("Name *", value=m.get('name', ''), key=f"u_nm_{m_id}", disabled=is_disabled)
                    m_rel = st.text_input("Relation *", value=m.get('relation', ''), key=f"u_rl_{m_id}",
                                          disabled=is_disabled)
                with c2:
                    m_dob = st.text_input("DOB * (YYYY-MM-DD)", value=str(m.get('dob', '')), key=f"u_db_{m_id}",
                                          disabled=is_disabled)
                    m_ph = st.text_input("Phone", value=m.get('phone', '') or '', key=f"u_ph_{m_id}",
                                         disabled=is_disabled)
                with c3:
                    m_em = st.text_input("Email", value=m.get('email', '') or '', key=f"u_em_{m_id}",
                                         disabled=is_disabled)
                    m_bg = st.text_input("Blood Group", value=m.get('blood_group', '') or '', key=f"u_bg_{m_id}",
                                         disabled=is_disabled)

                member_input_references.append({
                    "member_id": m_id, "name": m_name, "relation": m_rel, "dob": m_dob, "phone": m_ph, "email": m_em,
                    "blood_group": m_bg
                })
                st.write("")

            if st.session_state.form_edit_enabled:
                if st.form_submit_button("💾 Save All Modifications"):
                    db.update_family_header(f_id, f_head, f_illam, f_goth, f_addr)
                    for field in member_input_references:
                        db.admin_direct_save_member(field["member_id"], {
                            "name": field["name"], "relation": field["relation"], "dob": field["dob"],
                            "phone": field["phone"] if field["phone"] != "" else None,
                            "email": field["email"] if field["email"] != "" else None,
                            "blood_group": field["blood_group"] if field["blood_group"] != "" else None
                        })
                    st.success("✨ Complete household dataset successfully synchronized!")
                    st.session_state.form_edit_enabled = False
                    st.rerun()
            else:
                if st.form_submit_button("✅ Verify Data Is Correct & Complete"):
                    db.update_family_verification_state(f_id, "Data Verified")
                    st.success("Profile records verified and locked! Shifting execution to Payment interface.")
                    st.rerun()

    else:
        st.subheader("🏡 Household Summary (Locked)")
        st.info(
            f"📍 Head Name: {family_data.get('head_of_family')} | Illam: {family_data.get('illam_name')} | Gothram: {family_data.get('gothram')}")
        st.text(f"Master Address Path: {family_data.get('address')}")

    # --- ACTION WRAPPER B: INTERACTIVE CHECKOUT GATEWAY ---
    if v_status == "Data Verified":
        st.write("---")
        st.header("💳 Settle Annual Membership Dues")
        st.markdown(
            f"Please scan the QR matrix below or transfer the **₹{active_fee}** renewal fee using the listed UPI credentials.")

        live_upi_id = admin_cfg.get("upi_id", "sabha@upi")
        live_qr_url = admin_cfg.get("upi_qr_url", None)

        pay_layout_col1, pay_layout_col2 = st.columns([1, 2])
        with pay_layout_col1:
            if live_qr_url:
                st.image(live_qr_url, caption="Scan using GPay, PhonePe, or PayTM", use_container_width=True)
            else:
                st.warning("⚠️ QR code scanner matrix not uploaded by admin yet.")

        with pay_layout_col2:
            with st.container(border=True):
                st.markdown("### 📋 Payment Instructions")
                st.markdown(f"**Amount to Pay:** `₹{active_fee}`")
                st.markdown(f"**Official UPI ID:** `{live_upi_id}`")
                st.caption("💡 Hint: You can manually copy the UPI ID if your mobile phone scanner is unavailable.")

                st.write("---")
                with st.form("payment_submission_form"):
                    bank_ref_id = st.text_input("Enter Bank Transaction ID / UPI Ref Number (12 Digits) *").strip()
                    if st.form_submit_button("Submit Payment Reference Confirmation"):
                        if bank_ref_id == "":
                            st.error("Transaction reference code cannot be blank.")
                        else:
                            db.update_family_verification_state(f_id, "Payment Submitted", payment_ref=bank_ref_id)
                            st.success("Transaction token queued for treasury review!")
                            st.rerun()

    # --- ACTION WRAPPER C: DIGITAL TREASURY VOUCHER RECEIPT GENERATION ---
    if v_status == "Approved":
        st.write("---")
        st.subheader("📥 Central Treasury Receipts")
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
        st.download_button(
            label="📥 Download Printable Membership Receipt (TXT)",
            data=receipt_template,
            file_name=f"sabha_receipt_{current_year}_{f_id}.txt",
            mime="text/plain"
        )