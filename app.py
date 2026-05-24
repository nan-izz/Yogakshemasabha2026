import streamlit as st
import datetime
import csv
import io
import pandas as pd

import auth
import database as db

st.set_page_config(layout="wide")

# PWA Head Tags Injection
st.components.v1.html(
    """
    <head>
        <link rel="manifest" href="app/static/manifest.json">
        <meta name="theme-color" content="#ff4b4b">
        <meta name="apple-mobile-web-app-capable" content="yes">
    </head>
    """, height=0, width=0
)

# Session Initialization
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "family_id" not in st.session_state: st.session_state.family_id = None
if "auth_email" not in st.session_state: st.session_state.auth_email = None
if "otp_sent" not in st.session_state: st.session_state.otp_sent = False
if "login_mode" not in st.session_state: st.session_state.login_mode = "email"
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "admin_password_mode" not in st.session_state: st.session_state.admin_password_mode = False
if "register_mode" not in st.session_state: st.session_state.register_mode = False


def logout():
    st.session_state.clear()
    st.rerun()


main_display_viewport = st.container()

# -------------------------------------------------------------
# 1. IDENTITY AUTHENTICATION ENGINE
# -------------------------------------------------------------
if not st.session_state.logged_in:
    with main_display_viewport:
        st.title("Yogakshemasabha Portal")

        # ---- SUB-ROUTE: NEW HOUSEHOLD REGISTRATION FORM ----
        if st.session_state.register_mode:
            st.subheader("📝 Request New Household Registration")
            with st.form("new_family_reg_form"):
                reg_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name) *")
                reg_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name) *")
                reg_goth = st.text_input("ഗോത്രം (Gothram)")
                reg_email = st.text_input("Login Email ID *").strip().lower()
                reg_phone = st.text_input("Contact Phone Number *")
                reg_dob = st.date_input("Head of Family DOB *", value=datetime.date(1985, 1, 1))
                reg_addr = st.text_area("മേൽവിലാസം (Address) *")

                if st.form_submit_button("Submit Registration Request"):
                    if not reg_head or not reg_illam or not reg_email or not reg_phone or not reg_addr:
                        st.error("❌ Please fill in all mandatory fields.")
                    elif db.check_family_email_exists(reg_email):
                        st.error("🛑 This email is already linked to an existing registered profile.")
                    else:
                        db.submit_new_family_registration(reg_email, {
                            "head_of_family": reg_head.strip(), "illam_name": reg_illam.strip(),
                            "gothram": reg_goth.strip(), "email_id": reg_email.strip(),
                            "address": reg_addr.strip(), "head_phone": reg_phone.strip(),
                            "head_dob": reg_dob.strftime("%Y-%m-%d")
                        })
                        st.success("📩 Onboarding request successfully sent to the committee!")
                        st.session_state.register_mode = False
                        st.rerun()
            if st.button("← Back to Login"):
                st.session_state.register_mode = False
                st.rerun()

        # ---- MAIN ROUTE: STANDARD EMAIL / ADMIN INTERFACE ----
        elif st.session_state.login_mode == "email":
            st.subheader("Household Email / Admin Login")
            admin_cfg = db.fetch_admin_config()

            if not st.session_state.otp_sent and not st.session_state.admin_password_mode:
                input_email = st.text_input("Enter Email Identifier / Admin Username").strip().lower()

                if st.button("Proceed to Login"):
                    if input_email == admin_cfg["username"]:
                        st.session_state.auth_email = input_email
                        st.session_state.admin_password_mode = True
                        st.rerun()
                    elif "@" not in input_email or "." not in input_email:
                        st.error("❌ Please enter a valid email address.")
                    elif db.check_family_email_exists(input_email):

                        # --- TOAST / POPUP EXCEPTION PROTECTION ENGINE ---
                        try:
                            with st.spinner("Requesting secure login code from authentication servers..."):
                                db.send_supabase_otp(input_email)
                            st.session_state.auth_email = input_email
                            st.session_state.otp_sent = True
                            st.success(f"📩 Verification code sent successfully to {input_email}")
                            st.rerun()

                        except Exception as e:
                            # Capture raw error messages
                            error_msg = str(e)

                            # Check if it's the security rate-limit rule from Supabase
                            if "only request this after" in error_msg.lower():
                                # Extract the exact seconds remaining if present, or show a supportive message
                                st.warning(
                                    "⏳ **Slow down a bit!** A security login code was already sent to your inbox just a moment ago. To protect your profile, please wait roughly 30 seconds before requesting a new code.")
                            else:
                                # Fallback wrapper safety for any other unknown network errors
                                st.error(
                                    "⚠️ **Connection Timeout:** The authentication servers are currently busy or your mobile network connection dropped. Please check your signal bars and try tapping the button again.")
                    else:
                        st.error(
                            "🛑 This email is not registered. Use the onboarding link below if you are a new family.")
                st.write("---")
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("🔍 Alternative: Login Using Family Head & Illam Name"):
                        st.session_state.login_mode = "backdoor"
                        st.rerun()
                with col_b2:
                    if st.button("✨ New Family? Register New Household Profile here"):
                        st.session_state.register_mode = True
                        st.rerun()

            elif st.session_state.admin_password_mode:
                st.info(f"🛡️ Administrative Access Channel: **{st.session_state.auth_email}**")
                admin_pwd_input = st.text_input("Enter Admin Password", type="password")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Verify & Open Workspace"):
                        if admin_pwd_input == admin_cfg["password"]:
                            st.session_state.is_admin = True
                            st.session_state.logged_in = True
                            st.rerun()
                        else:
                            st.error("❌ Invalid Administrative Password Credential.")
                with col2:
                    if st.button("← Cancel"):
                        st.session_state.admin_password_mode = False
                        st.session_state.auth_email = None
                        st.rerun()

                    # ---- FIXED STATE C: STANDARD USER INTERACTIVE OTP ENTRY (MOBILE SECURE) ----
            elif st.session_state.otp_sent:
                st.info(f"📩 Logging into Household Profile: **{st.session_state.auth_email}**")

                with st.form("mobile_secure_otp_form"):
                    otp_token = st.text_input("Enter the 6-Digit Verification Code sent to your inbox",
                                                      max_chars=6).strip()
                    submit_otp = st.form_submit_button("Verify Code & Open Dashboard", use_container_width=True)

                    if submit_otp:
                        if otp_token == "" or len(otp_token) < 6:
                            st.error("❌ Please enter a valid 6-digit verification code.")
                        else:
                            with st.spinner("Verifying token with authentication servers..."):
                                # CRITICAL SECURITY CHECK: Validates token against Supabase ledger
                                is_otp_valid = db.verify_supabase_otp(st.session_state.auth_email, otp_token)

                            if is_otp_valid:
                                family_lookup = db.fetch_family_by_email(st.session_state.auth_email)
                                if family_lookup:
                                    st.session_state.family_id = family_lookup["family_id"]
                                    st.session_state.logged_in = True
                                    st.success("🎉 Access Granted! Loading dashboard...")
                                    st.rerun()
                                else:
                                    st.error("❌ Link broken. Household profile mismatch.")
                            else:
                                st.error(
                                    "🛑 Invalid or expired verification code. Please check your inbox or try again.")

                if st.button("← Cancel & Try Different Email", use_container_width=True):
                    st.session_state.otp_sent = False
                    st.session_state.auth_email = None
                    st.rerun()

        elif st.session_state.login_mode == "backdoor":
            st.subheader("Verify via Household Details (No Email Connected)")
            input_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)").strip()
            input_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)").strip()

            if st.button("Find and Verify Profile"):
                records = db.verify_backdoor_details(input_head, input_illam)
                if records:
                    found = records[0]
                    if found.get("email_id") and str(found.get("email_id")).strip() != "" and str(
                            found.get("email_id")).lower() != "none":
                        st.error(
                            f"🛑 Security Block: This household profile has already been assigned an email ({found['email_id']}). You must use email verification.")
                    else:
                        st.session_state.family_id = found["family_id"]
                        st.session_state.logged_in = True
                        st.rerun()
                else:
                    st.error("❌ Authentication Failed. No matching record found inside the Sabha directories.")

            if st.button("← Back to Standard Email Login"):
                st.session_state.login_mode = "email"
                st.rerun()

# -------------------------------------------------------------
# 2. THE MASTER CONTROL PANEL (ADMINISTRATION PORTAL)
# -------------------------------------------------------------
elif st.session_state.is_admin:
    st.sidebar.title("🛡️ Admin Workspace")
    if st.sidebar.button("Secure Log Out"): logout()

    with main_display_viewport:
        admin_tab = st.tabs(["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "🎂 Age Verification Filter",
                             "⚙️ Admin Settings"])

        # ---- ADMIN TAB 1: TABLE-BASED AUDIT PIPELINE QUEUE ----
        with admin_tab[0]:
            st.header("Modifications Awaiting Administrative Clearance")
            st.subheader("💳 Staged Subscription Confirmations")

            admin_cfg = db.fetch_admin_config()
            db_base_fee = admin_cfg.get("base_family_fee", 700)
            db_threshold = admin_cfg.get("base_member_threshold", 4)
            db_add_fee = admin_cfg.get("additional_member_fee", 100)

            all_households = db.fetch_all_families_global()
            payment_requests = [x for x in all_households if x.get("verification_status") == "Payment Submitted"]

            for p_req in payment_requests:
                f_m_records = db.fetch_family_members(p_req['family_id'])
                adm_h_count = len(f_m_records) if f_m_records else 1
                adm_expected_fee = int(db_base_fee) if adm_h_count <= int(db_threshold) else int(db_base_fee) + (
                            (adm_h_count - int(db_threshold)) * int(db_add_fee))

                with st.container(border=True):
                    st.write(f"🏡 **{p_req['head_of_family']}** | Dues Expected: **₹{adm_expected_fee}**")
                    st.markdown(
                        f"<div style='background-color:#f1f3f5; padding:8px; border-radius:6px; font-size:14px; display:inline-block;'>👥 Roster Breakdown: <b>{adm_h_count} members</b></div>",
                        unsafe_allow_html=True)
                    st.write(f"Reference Code: `{p_req['payment_reference']}`")
                    c_p1, c_p2 = st.columns(2)
                    with c_p1:
                        if st.button("✅ Verify Payment", key=f"pay_app_{p_req['family_id']}"):
                            db.update_family_verification_state(p_req['family_id'], "Approved")
                            st.rerun()
                    with c_p2:
                        if st.button("❌ Reject Payment Log", key=f"pay_rej_{p_req['family_id']}"):
                            db.update_family_verification_state(p_req['family_id'], "Pending Update")
                            st.rerun()

            st.write("---")
            st.subheader("📝 Pending Profile Core Alterations")
            pending_data = db.fetch_pending_approvals()

            # User-friendly column name translation dictionary
            FIELD_MAP = {
            "head_of_family": "Household Head Name",
            "illam_name": "Illam Name",
            "gothram": "Gothram",
            "address": "Master Address",
            "name": "Member Name",
            "relation": "Relationship to Head",
            "dob": "Date of Birth",
            "blood_group": "Blood Group",
            "phone": "Phone Number",
            "email": "Email Address",
            "qualification": "Educational Qualification",
            "job": "Occupation / Job",
            "adhaar": "Aadhaar Number",
            "current_address": "Current Residential Address"
            }

            for req in pending_data:
                req_id, table, action, payload, target_row_id = req["approval_id"], req["target_table"], req["action_type"], \
                req["change_payload"] or {}, req["target_id"]

                # Filter out system primary/foreign keys that basic users don't see
                hidden_keys = ["family_id", "member_id", "id", "updated_at", "created_at", "verification_status"]
                display_payload = {FIELD_MAP.get(k, k): v for k, v in payload.items() if
                               k not in hidden_keys and v is not None}

                with st.container(border=True):
                    st.markdown(f"#### ✉️ Request #{req_id}: **{action}** on **{table.upper()}**")
                    st.caption(f"Submitted by: {req['requested_by']}")

                # 🟢 SCENARIO 1: NEW ENTRY (INSERT)
                    if action == "INSERT":
                        st.info("✨ **Action Type: New Profile Registration Request**")
                        st.markdown("**Below is the full data that will be added to the registry:**")

                        # Display data cleanly in a two-column structural grid
                        idx_c1, idx_c2 = st.columns(2)
                        for i, (k, v) in enumerate(display_payload.items()):
                            with idx_c1 if i % 2 == 0 else idx_c2:
                                st.markdown(f"🔹 **{k}:** {v}")

                    # 🔴 SCENARIO 2: REMOVAL OPERATION (DELETE)
                    elif action == "DELETE":
                        st.error("🗑️ **Action Type: Profile Deletion Request**")
                        st.markdown("**The following registered entity profile is targeted for permanent removal:**")

                        # Grab context identifiers safely based on targeted table mapping
                        entity_title = payload.get("name") or payload.get("head_of_family") or f"ID #{target_row_id}"
                        st.markdown(
                        f"⚠️ **Target Entity:** <span style='font-size:16px; font-weight:700; color:#ff4b4b;'>{entity_title}</span>",
                        unsafe_allow_html=True)
                        if "relation" in payload:
                            st.markdown(f"🔹 *Relationship Alignment:* {payload['relation']}")

                    # 🟡 SCENARIO 3: MODIFICATION DELTA (UPDATE)
                    elif action == "UPDATE":
                        st.warning("🔄 **Action Type: Profile Modification Request**")
                        st.markdown("**Changes requested inside this record:**")

                        #Fetch the original master record from the database to compare differences
                        if table == "families":
                            current_master = db.fetch_single_family(target_row_id)
                            context_name = f"Household: {current_master.get('head_of_family')} | ഇല്ലം: {current_master.get('illam_name')}"
                        else:
                            # Pull individual member context info
                            m_lookup = db.supabase.table("members").select("*").eq("member_id", target_row_id).execute()
                            current_master = m_lookup.data[0] if m_lookup.data else {}
                            context_name = f"Member Profile: **{current_master.get('name', 'Unknown')}** ({current_master.get('relation', 'Member')})"

                        st.markdown(f"📍 **Target Profile Context:** {context_name}")
                        st.write("")

                        # Build a dynamic comparison checklist matrix table layout
                        comp_rows = []
                        for raw_key, new_val in payload.items():
                            if raw_key in hidden_keys: continue

                            old_val = current_master.get(raw_key, "N/A")
                            # Normalize comparisons to avoid blank space string mismatches
                            if str(old_val).strip() == "" or old_val is None: old_val = "*(Empty / Unconfigured)*"
                            if str(new_val).strip() == "" or new_val is None: new_val = "*(Set to Blank / Clear)*"

                            if str(old_val) != str(new_val):
                                friendly_key = FIELD_MAP.get(raw_key, raw_key)
                                comp_rows.append({
                                "Modified Property Field": friendly_key,
                                "🔴 Current Value on Live Server": str(old_val),
                                "🟢 New Proposed Value Overwrite": str(new_val)
                                })

                        if comp_rows:
                            st.table(pd.DataFrame(comp_rows))
                        else:
                            st.info(
                            "ℹ️ No textual property differences discovered. (User submitted layout form without overwriting entries)")

                    st.write("")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("👍 Approve Change", key=f"appr_{req_id}"):
                            db.process_approval_action(req_id, action, table, payload, target_row_id)
                            if table == "members" and target_row_id:
                                m_look = db.supabase.table("members").select("family_id").eq("member_id",
                                                                                         target_row_id).execute()
                                if m_look.data: db.update_family_verification_state(m_look.data[0]["family_id"],
                                                                                "Pending Update")
                            st.success("Changes approved successfully!")
                            st.rerun()
                    with c2:
                        if st.button("👎 Reject Change", key=f"rej_{req_id}"):
                            db.reject_pending_approval(req_id)
                            st.rerun()

        # ---- ADMIN TAB 2: GLOBAL DIRECTORY SEARCH MATRIX (EDITABLE TARGET VIEWS RESTORED) ----
        with admin_tab[1]:
            st.header("Global Directory Master Tracking View")

            search_q = st.text_input(
                "🔍 Search over Head Name, Illam or Address (Leave blank for default tracking views)").strip()

            if search_q == "":
                st.subheader("⏱️ Last 10 Recently Updated Households")
                display_fams = db.fetch_recent_families_global(limit=10)
            else:
                st.subheader(f"🎯 Search Query Results for: '{search_q}'")
                display_fams = db.search_families_global(search_q)

            if not display_fams:
                st.info("No matching records found in directories.")
            else:
                for f in display_fams:
                    if f["family_id"] == 999999: continue

                    exp_label = f"🏡 {f.get('head_of_family')} | ഇല്ലം: {f.get('illam_name')} | Status: {f.get('verification_status', 'Pending Update')}"
                    with st.expander(exp_label):

                        if not f.get("email_id"):
                            pre_reg_email = st.text_input("Enter Email to bind to this profile",
                                                          key=f"pr_em_txt_{f['family_id']}").strip().lower()
                            if st.button("🔗 Direct Pre-Register & Bind Email", key=f"pr_em_btn_{f['family_id']}"):
                                if "@" not in pre_reg_email or "." not in pre_reg_email:
                                    st.error("Invalid email format.")
                                else:
                                    db.link_family_email(f['family_id'], pre_reg_email)
                                    st.success("Email bound successfully!")
                                    st.rerun()
                        else:
                            st.info(f"Registered Login Identifier Email: **{f['email_id']}**")
                            if st.button("🔄 Reset Linked Email Address", key=f"rst_{f['family_id']}"):
                                db.link_family_email(f['family_id'], None)
                                st.success("Identity reset completed.")
                                st.rerun()

                        st.write("---")
                        # Header details form
                        with st.form(f"adm_fam_form_{f['family_id']}"):
                            st.markdown("#### 🛠️ Edit Household Core Header Information")
                            a_head = st.text_input("Head of Family Name", value=f["head_of_family"])
                            a_illam = st.text_input("Illam Name", value=f["illam_name"])
                            a_goth = st.text_input("Gothram", value=f.get("gothram", ""))
                            a_addr = st.text_area("Master Address Line", value=f["address"])

                            b_cols = st.columns([4, 1])
                            with b_cols[0]:
                                if st.form_submit_button("💾 Direct Save Header Changes"):
                                    db.update_family_header(f['family_id'], a_head, a_illam, a_goth, a_addr)
                                    st.success("Header details updated directly!")
                                    st.rerun()
                            with b_cols[1]:
                                if st.form_submit_button("❌ Drop Household"):
                                    db.admin_direct_delete_family(f['family_id'])
                                    st.warning("Household entity completely dropped.")
                                    st.rerun()

                        st.write("---")
                        # Family members editable profiles registry
                        st.markdown("#### 👥 Core Family Members Registry Details")
                        m_records = db.fetch_family_members(f['family_id'])

                        if not m_records:
                            st.info("No members mapped to this household yet.")
                        else:
                            for m in m_records:
                                with st.container(border=True):
                                    with st.form(f"adm_mem_form_{m['member_id']}"):
                                        st.markdown(f"##### Member Profile Card: **{m['name']}**")

                                        mc1, mc2 = st.columns(2)
                                        with mc1:
                                            ma_name = st.text_input("Full Name", value=m["name"])
                                            ma_rel = st.text_input("Relation to Head", value=m["relation"])
                                            ma_dob = st.text_input("DOB (YYYY-MM-DD)",
                                                                   value=str(m["dob"]) if m.get("dob") else "")
                                            ma_bg = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS,
                                                                 index=auth.BLOOD_GROUPS.index(
                                                                     m["blood_group"]) if m.get(
                                                                     "blood_group") in auth.BLOOD_GROUPS else 0)
                                        with mc2:
                                            ma_phone = st.text_input("Phone Number", value=m.get("phone", ""))
                                            ma_email = st.text_input("Email", value=m.get("email", ""))
                                            ma_qual = st.text_input("Qualification", value=m.get("qualification", ""))
                                            ma_job = st.text_input("Occupation / Job", value=m.get("job", ""))

                                        ma_adh = st.text_input("Aadhaar Number", value=m.get("adhaar", ""))
                                        ma_caddr = st.text_area("Current Residential Address",
                                                                value=m.get("current_address", ""))

                                        m_cols = st.columns([4, 1])
                                        with m_cols[0]:
                                            if st.form_submit_button("💾 Save Member Direct Updates"):
                                                is_valid, clean_a = auth.validate_aadhaar(ma_adh)
                                                if ma_name.strip() == "" or ma_rel.strip() == "" or ma_dob.strip() == "":
                                                    st.error("Fields marked with * are mandatory parameters.")
                                                elif not is_valid:
                                                    st.error("Invalid Aadhaar formatting configuration.")
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
                                                    st.success("Member updates pushed directly!")
                                                    st.rerun()
                                        with m_cols[1]:
                                            if st.form_submit_button("❌ Drop Member"):
                                                db.admin_direct_delete_member(m['member_id'])
                                                st.warning("Member dropped from registry.")
                                                st.rerun()

        # ---- ADMIN TAB 3: AGE VERIFICATION & DISTRICT SABHA REPORTS ----
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
                with st.spinner("Compiling structural database report matrix..."):
                    raw_members = db.fetch_all_members_global()
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
                                       file_name=f"district_sabha_{current_year}.csv", mime="text/csv")

        # ---- ADMIN TAB 4: SYSTEM CONFIGS (RESTORED COMPLETELY) ----
        with admin_tab[3]:
            st.header("Security & Subscription Configuration Settings")
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
            # RESTORED UPI ID AND QR ASSET CONFIGURATION TRACK PANEL
            st.subheader("💳 Configure Sabha Treasury UPI Parameters & QR Gateway")
            with st.form("admin_upi_configuration_form"):
                new_upi_id = st.text_input("Sabha Official UPI ID / VPA Handle",
                                           value=current_config.get("upi_id", "sabha@upi")).strip()
                uploaded_qr = st.file_uploader("Upload Official UPI QR Code Image (PNG/JPG)",
                                               type=["png", "jpg", "jpeg"])
                if st.form_submit_button("Update Payment Gateway Assets"):
                    if new_upi_id == "":
                        st.error("UPI address handle cannot be left blank.")
                    else:
                        db.update_admin_upi_credentials(new_upi_id, uploaded_qr.getvalue() if uploaded_qr else None)
                        st.success("🔒 Treasury billing gateway assets updated successfully!")
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
# 3. STANDARD USER WORKSPACE (PERMANENTLY UNLOCKED)
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

    member_count = len(members_data) if members_data else 1
    active_fee = int(admin_cfg["base_family_fee"]) if member_count <= int(admin_cfg["base_member_threshold"]) else int(
        admin_cfg["base_family_fee"]) + ((member_count - int(admin_cfg["base_member_threshold"])) * int(
        admin_cfg["additional_member_fee"]))

    st.title("Yogakshemasabha Household Terminal")

    notification_msg = family_data.get("admin_notification")
    if notification_msg:
        st.info(notification_msg)
        if st.button("Dismiss Notification"): db.clear_user_notification(f_id); st.rerun()

    is_disabled = False
    # === PASTE STEP 3 DIRECTLY HERE ===
    # --- CROSS-RERUN PERSISTENT BANNER DISPLAY LOGIC ---
    if "roster_success_msg" in st.session_state and st.session_state.roster_success_msg:
        st.success(st.session_state.roster_success_msg)
        st.session_state.roster_success_msg = None
    user_tabs = st.tabs(["🏡 Household Profile", "👥 Family Members Roster", "📋 Verify & Settle Dues"])

    # ---- TAB 1: HOUSEHOLD IDENTITY HEADER (STAGED FOR ADMINISTRATIVE APPROVAL) ----
    with user_tabs[0]:
        st.write("")
        with st.form("edit_family_header_modular_form"):
            st.markdown("#### 🛠️ Request Changes to Household Core Information")

            h_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name) *",
                                   value=family_data.get('head_of_family', ''))
            h_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name) *", value=family_data.get('illam_name', ''))
            h_goth = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
            h_addr = st.text_area("മേൽവിലാസം (Address) *", value=family_data.get('address', ''))

            if st.form_submit_button("💾 Submit Profile Updates to Committee"):
                if h_head.strip() == "" or h_illam.strip() == "" or h_addr.strip() == "":
                    st.error("❌ Mandatory parameters (Head Name, Illam Name, and Address) cannot be left blank.")
                else:
                    # ROUTE TO QUEUE: Instead of db.update_family_header, we pass it to the staging queue
                    db.submit_pending_approval(
                        table="families",
                        action="UPDATE",
                        requested_by=st.session_state.auth_email,
                        payload={
                            "head_of_family": h_head.strip(),
                            "illam_name": h_illam.strip(),
                            "gothram": h_goth.strip() if h_goth.strip() != "" else None,
                            "address": h_addr.strip()
                        },
                        target_id=f_id
                    )

                    # Store the custom persistent notification string into session memory
                    st.session_state.roster_success_msg = "📩 **Household Changes Staged Successfully!** Your core header updates have been submitted to the committee queue for review. You will see them applied once an administrator signs off."

                    # Set the workflow timeline map status back to Step 1
                    db.update_family_verification_state(f_id, "Pending Update")
                    st.rerun()

            # ---- TAB 2: MEMBERS MANAGEMENT ROSTER (FIXED SINGLE-CARD SAVING) ----
    with user_tabs[1]:
        st.write("")
        header_address = family_data.get('address', '').strip()

        if not members_data:
            st.info("ℹ️ No family members mapped yet.")
        else:
            # Notice: The giant global st.form container has been removed from here!
            for m in members_data:
                m_id = m['member_id']

                # Each member profile gets their own independent isolated form container
                with st.form(key=f"user_member_form_standalone_{m_id}"):
                    st.markdown(f"#### 👤 {m['name']} ({m['relation'] or 'Member'})")

                    # Create the layout split columns
                    c1, c2 = st.columns(2)
                    with c1:
                        m_name = st.text_input("Name *", value=m.get('name', ''))
                        try:
                            parsed_dob = datetime.datetime.strptime(str(m.get('dob', '1990-01-01')), "%Y-%m-%d").date()
                        except:
                            parsed_dob = datetime.date(1990, 1, 1)
                        final_dob = st.date_input("DOB *", value=parsed_dob)
                        m_phone = st.text_input("Phone Number", value=str(m.get('phone', '')) if m.get('phone') else '')
                        m_qual = st.text_input("Qualification", value=m.get('qualification', '') or '')
                    with c2:
                        m_rel = st.text_input("Relation *", value=m.get('relation', ''))
                        m_bg = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS,
                                            index=auth.BLOOD_GROUPS.index(m['blood_group']) if m.get(
                                                'blood_group') in auth.BLOOD_GROUPS else 0)
                        m_email = st.text_input("Email", value=m.get('email', '') or '')
                        m_job = st.text_input("Job / Occupation", value=m.get('job', '') or '')

                    st.write("---")
                    # Aadhaar and addresses stay down here across the full width...
                    m_adhaar = st.text_input("Aadhaar Number",
                                                     value=str(m.get('adhaar', '')) if m.get('adhaar') else '')
                    is_same_initial = (m.get('current_address', '').strip() == header_address or m.get(
                                'current_address', '').strip() == "")

                    m_addr_sel = st.radio("Current Address Context Selector",
                                                  options=["Same as Household Address", "Custom Address"],
                                                  index=0 if is_same_initial else 1, key=f"addr_rad_{m_id}")

                    if m_addr_sel == "Custom Address":
                        m_caddr = st.text_area("Enter Custom Current Address", value=m.get('current_address',
                                                                                                   '') if not is_same_initial else "")
                    else:
                        m_caddr = ""

                    st.write("")
                    m_delete_tick = st.checkbox("🗑️ Request Deletion of this Member Record")

                    # This save button ONLY processes this specific individual card!
                    if st.form_submit_button(f"💾 Save Changes for {m['name']}"):
                        if m_delete_tick:
                            db.submit_pending_approval("members", "DELETE", st.session_state.auth_email,
                                                               {"name": m_name}, target_id=m_id)
                            st.session_state.roster_success_msg = f"📩 **Deletion Request Staged!** Request to remove {m_name} sent to the committee queue."
                            db.update_family_verification_state(f_id, "Pending Update")
                            st.rerun()
                        else:
                            is_valid, clean_a = auth.validate_aadhaar(m_adhaar)
                            if m_name.strip() == "" or m_rel.strip() == "":
                                st.error("❌ Name and Relation are mandatory fields.")
                            elif m_adhaar.strip() != "" and not is_valid:
                                st.error(
                                    "❌ Invalid Aadhaar number syntax. It must be exactly 12 numeric digits.")
                            else:
                                final_m_addr = header_address if m_addr_sel == "Same as Household Address" else m_caddr.strip()

                                clean_phone = m_phone.strip() if m_phone and m_phone.strip() != "" else None
                                clean_adh = clean_a if clean_a and clean_a.strip() != "" else None
                                clean_email = m_email.strip() if m_email and m_email.strip() != "" else None
                                clean_qual = m_qual.strip() if m_qual and m_qual.strip() != "" else None
                                clean_job = m_job.strip() if m_job and m_job.strip() != "" else None

                                db.submit_pending_approval("members", "UPDATE", st.session_state.auth_email, {
                                            "name": m_name.strip(),
                                            "relation": m_rel.strip(),
                                            "dob": m_dob.strftime("%Y-%m-%d"),
                                            "blood_group": None if m_bg == 'Not Identified' else m_bg,
                                            "phone": clean_phone,
                                            "email": clean_email,
                                            "qualification": clean_qual,
                                            "job": clean_job,
                                            "adhaar": clean_adh,
                                            "current_address": final_m_addr
                                        }, target_id=m_id)

                                st.session_state.roster_success_msg = f"📩 **Changes Staged Successfully!** Modifications for **{m_name}** sent to the committee queue."
                                db.update_family_verification_state(f_id, "Pending Update")
                                st.rerun()

        with st.expander("➕ Request Adding a New Member to this Household"):
            n_name = st.text_input("Full Name *", key="n_name")
            n_rel = st.text_input("Relation *", key="n_rel")
            n_dob = st.date_input("DOB *", value=datetime.date(1995, 1, 1), key="n_dob")
            n_blood = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS, key="n_bg")
            n_phone = st.text_input("Phone Number", key="n_phone")
            n_email = st.text_input("Email Address", key="n_email")
            n_qual = st.text_input("Qualification", key="n_qual")
            n_job = st.text_input("Job / Profession", key="n_job")
            n_adhaar = st.text_input("Aadhaar Number", key="n_adhaar")
            n_addr_sel = st.radio("Current Address", options=["Same as Household Address", "Custom Address"], index=0,
                                  key="n_rad")
            n_custom_addr = st.text_area("Custom Address String", key="n_txa") if n_addr_sel == "Custom Address" else ""

            if st.button("Submit New Member Profile to Queue"):
                # ENFORCED PARAMETERS CHECK: Verifies Name and Relation are not blank strings
                if n_name.strip() == "" or n_rel.strip() == "":
                    st.error("❌ Mandatory parameters missing: You must enter a valid Name and Relation to continue.")
                else:
                    is_valid, clean_a = auth.validate_aadhaar(n_adhaar)
                    if n_adhaar.strip() != "" and not is_valid:
                        st.error("❌ Invalid Aadhaar number syntax. It must be exactly 12 numeric digits.")
                    else:
                        # DATA SCRUBBING FOR DATATYPE INTERLOCK SAFETY
                        clean_n_phone = n_phone.strip() if n_phone and n_phone.strip() != "" else None
                        clean_n_adh = clean_a if clean_a and clean_a.strip() != "" else None
                        clean_n_email = n_email.strip() if n_email and n_email.strip() != "" else None
                        clean_n_qual = n_qual.strip() if n_qual and n_qual.strip() != "" else None
                        clean_n_job = n_job.strip() if n_job and n_job.strip() != "" else None
                        final_n_addr = header_address if n_addr_sel == "Same as Household Address" else n_custom_addr.strip()

                        db.submit_pending_approval("members", "INSERT", st.session_state.auth_email, {
                            "family_id": f_id,
                            "name": n_name.strip(),
                            "relation": n_rel.strip(),
                            "dob": n_dob.strftime("%Y-%m-%d"),
                            "blood_group": None if n_blood == 'Not Identified' else n_blood,
                            "phone": clean_n_phone,
                            "email": clean_n_email,
                            "qualification": clean_n_qual,
                            "job": clean_n_job,
                            "adhaar": clean_n_adh,
                            "current_address": final_n_addr
                        })

                        # Save the banner data token into state memory
                        st.session_state.roster_success_msg = "📩 **Addition Request Staged successfully!** The new profile has been sent to the committee queue for approval. Once reviewed by an administrator, your household summary page will be refreshed."

                        db.update_family_verification_state(f_id, "Pending Update")
                        st.rerun()

    # ---- TAB 3: THE SEPARATE PROGRESSIVE VERIFICATION TUNNEL PANEL ----
    with user_tabs[2]:
        st.write("")
        if not is_audit_window:
            st.info(
                "ℹ️ Institutional dues settlement gates are currently closed outside active verification tracking cycles.")
        else:
            is_user_stuck_in_queue = db.check_if_user_has_pending_requests(st.session_state.auth_email)
            is_awaiting_payment_clearance = (v_status == "Payment Submitted")

            st.markdown("### 🗺️ Your Progress Map")
            if is_user_stuck_in_queue:
                st.markdown(
                    "<div style='background-color:#fff3cd; padding:12px; border-radius:8px; text-align:center; font-weight:700; color:#856404;'>⏳ STEP 1: Waiting for Committee Approval of Your Recent Edits</div>",
                    unsafe_allow_html=True)
            elif v_status == "Pending Update":
                st.markdown(
                    "<div style='background-color:#e8f4fd; padding:12px; border-radius:8px; text-align:center; font-weight:700; color:#004085;'>🔍 STEP 1: Please Check and Confirm Your Family Details Below</div>",
                    unsafe_allow_html=True)
            elif v_status == "Data Verified":
                st.markdown(
                    "<div style='background-color:#d4edda; padding:12px; border-radius:8px; text-align:center; font-weight:700; color:#155724;'>💳 STEP 2: Scan QR Code Below to Complete Your Payment</div>",
                    unsafe_allow_html=True)
            elif is_awaiting_payment_clearance:
                st.markdown(
                    "<div style='background-color:#e2e3e5; padding:12px; border-radius:8px; text-align:center; font-weight:700; color:#383d41;'>⏳ STEP 3: Payment Submitted! Awaiting Committee Cross-Check</div>",
                    unsafe_allow_html=True)
            elif v_status == "Approved":
                st.markdown(
                    "<div style='background-color:#d4edda; padding:12px; border-radius:8px; text-align:center; font-weight:700; color:#155724;'>🎉 STEP 4: Registration Fully Approved! Your Receipt is Ready Below</div>",
                    unsafe_allow_html=True)

            st.write("---")

            if is_user_stuck_in_queue:
                st.markdown("#### ⏳ Verification Paused Dynamically")
                st.warning(
                    "You have recently saved changes to your family profile that are waiting to be approved by the committee secretary. **As soon as the committee approves your changes, this page will automatically unlock** so you can check them and pay.")

            elif is_awaiting_payment_clearance:
                st.markdown("#### ⏳ Payment Under Review")
                st.info(
                    f"Your payment reference number (`{family_data.get('payment_reference')}`) has been successfully sent to the Sabha Treasurer. Once verified against the bank statement, your receipt will unlock below.")

            elif v_status == "Approved":
                st.balloons()
                st.markdown("### 📥 Download Your Official Payment Receipt")
                st.success("Thank you! Your yearly membership subscription has been cleared.")
                current_year = datetime.date.today().year
                receipt_template = f"====================================================\n          YOGAKSHEMASABHA CENTRAL TREASURY\n                OFFICIAL PAYMENT RECEIPT\n====================================================\nReceipt Date: {datetime.date.today().strftime('%d-%B-%Y')}\nHousehold Unit: {family_data.get('head_of_family')} \nIllam Name: {family_data.get('illam_name')} \nTotal Members: {member_count} Profile Logs Saved\nAmount Paid: INR {active_fee}.00\nStatus: CLEAR / FULLY VERIFIED CORPS\n===================================================="
                st.code(receipt_template, language="text")
                st.download_button(label="📥 Click Here to Download & Print Receipt", data=receipt_template,
                                   file_name=f"sabha_receipt_{f_id}.txt", mime="text/plain")

            else:
                st.markdown("### 📋 Step 1: Review Your Final Family Summary")
                st.caption(
                    "Please check this official summary. If anything looks incorrect, simply click **Tab 1** or **Tab 2** above to change it. Your corrections will show up here instantly.")

                b_col1, b_col2, b_col3 = st.columns(3)
                with b_col1:
                    st.markdown(
                        f"<div style='background-color:#f8f9fa; padding:15px; border-radius:10px; border-left:5px solid #ff4b4b;'><b>🏡 Head of Family:</b><br><span style='font-size:18px; font-weight:700;'>{family_data.get('head_of_family')}</span></div>",
                        unsafe_allow_html=True)
                with b_col2:
                    st.markdown(
                        f"<div style='background-color:#f8f9fa; padding:15px; border-radius:10px; border-left:5px solid #0068c9;'><b>🏘️ Illam Name:</b><br><span style='font-size:18px; font-weight:700;'>{family_data.get('illam_name')}</span></div>",
                        unsafe_allow_html=True)
                with b_col3:
                    st.markdown(
                        f"<div style='background-color:#f8f9fa; padding:15px; border-radius:10px; border-left:5px solid #29b6f6;'><b>👥 Roster Headcount:</b><br><span style='font-size:18px; font-weight:700;'>{member_count} Members</span></div>",
                        unsafe_allow_html=True)

                st.write("")
                clean_members = []
                for idx, m in enumerate(members_data, start=1):
                    clean_members.append(
                        {"Sl No": idx, "Family Member Name": m["name"], "Relationship": m["relation"] or "Member",
                         "Date of Birth": m["dob"], "Phone Number": m["phone"] or "N/A"})
                st.table(pd.DataFrame(clean_members))

                st.write("---")

                if v_status == "Pending Update":
                    st.markdown("#### ⚠️ Confirm Your Roster Accuracy")
                    st.write(
                        "If all the names and numbers listed above are entirely correct, please click the big green confirmation button below to open up the payment options.")
                    st.write("")

                    if st.button("👉 YES, everything listed above is correct! Show payment details.", type="primary",
                                 use_container_width=True):
                        db.update_family_verification_state(f_id, "Data Verified")
                        st.success("Roster verified! Checkout options unlocked below.")
                        st.rerun()

                elif v_status == "Data Verified":
                    st.markdown("### 💳 Step 2: Pay Your Annual Membership Fee")

                    pay_layout_col1, pay_layout_col2 = st.columns([2, 3])
                    with pay_layout_col1:
                        with st.container(border=True):
                            st.markdown(
                                "<p style='text-align:center; font-weight:700; margin-bottom:5px; color:#495057;'>🖨️ SCAN THE QR CODE TO PAY</p>",
                                unsafe_allow_html=True)
                            if admin_cfg.get("upi_qr_url"):
                                st.image(admin_cfg["upi_qr_url"], use_container_width=True)
                            else:
                                st.warning("⚠️ Official QR asset unavailable.")

                    with pay_layout_col2:
                        st.markdown(f"""
                            <div style='background-color:#e8f4fd; padding:15px; border-radius:8px; margin-bottom:15px; border-left:5px solid #0056b3;'>
                                🏷️ <b>Subscription Fee Due:</b> <span style='font-size:20px; font-weight:700; color:#ff4b4b;'>₹{active_fee}</span><br>
                                🎯 <b>Official Sabha Bank UPI Address:</b> <code style='font-size:14px; font-weight:700; color:#0056b3;'>{admin_cfg.get('upi_id', 'sabha@upi')}</code>
                            </div>
                        """, unsafe_allow_html=True)

                        upi_string = f"upi://pay?pa={admin_cfg.get('upi_id', 'sabha@upi')}&pn=Yogakshemasabha&am={active_fee}&cu=INR"
                        st.link_button("📱 If using a phone, click here to pay instantly with your banking apps",
                                       upi_string, use_container_width=True)

                        st.write("---")
                        with st.form("payment_submission_form"):
                            bank_ref_id = st.text_input("Type your 12-digit payment reference number here:").strip()
                            if st.form_submit_button("🔒 Click Here to Send Reference Number to Treasurer",
                                                     use_container_width=True):
                                if bank_ref_id == "" or len(bank_ref_id) < 6:
                                    st.error("❌ Please check the number you typed. It cannot be blank or incomplete.")
                                else:
                                    db.update_family_verification_state(f_id, "Payment Submitted",
                                                                        payment_ref=bank_ref_id)
                                    st.success("Success! Reference token logged.")
                                    st.rerun()