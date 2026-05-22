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
    </head>
    """, height=0, width=0
)

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
# 1. IDENTITY AUTHENTICATION ENGINE (ISOLATED EXECUTION LAYER)
# -------------------------------------------------------------
if not st.session_state.logged_in:
    with main_display_viewport:
        st.title("Yogakshemasabha Portal")

        if st.session_state.register_mode:
            st.subheader("📝 Request New Household Registration")
            with st.form("new_family_reg_form"):
                reg_head = st.text_input("ഗൃഹനാഥന്റെ പേര് *")
                reg_illam = st.text_input("ഇല്ലപ്പേര് *")
                reg_goth = st.text_input("ഗോത്രം")
                reg_email = st.text_input("Login Email ID *").strip().lower()
                reg_phone = st.text_input("Contact Phone Number *")
                reg_dob = st.date_input("Head of Family DOB *", value=datetime.date(1985, 1, 1))
                reg_addr = st.text_area("മേൽവിലാസം *")

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
                        st.success("📩 Request sent successfully!")
                        st.session_state.register_mode = False
                        st.rerun()
            if st.button("← Back to Login"):
                st.session_state.register_mode = False
                st.rerun()

        elif st.session_state.login_mode == "email":
            st.subheader("Household Email / Admin Login")
            admin_cfg = db.fetch_admin_config()
            input_email = st.text_input("Enter Email Identifier / Admin Username").strip().lower()

            if st.button("Proceed to Login"):
                if input_email == admin_cfg["username"]:
                    st.session_state.auth_email = input_email
                    st.session_state.admin_password_mode = True
                    st.rerun()
                elif db.check_family_email_exists(input_email):
                    db.send_supabase_otp(input_email)
                    st.session_state.auth_email = input_email
                    st.session_state.otp_sent = True
                    st.success(f"Verification code sent to {input_email}")
                    st.rerun()
                else:
                    st.error("Email identifier not found in records.")
            st.write("---")
            if st.button("✨ New Family? Register Household Profile Here"):
                st.session_state.register_mode = True
                st.rerun()

        elif st.session_state.admin_password_mode:
            admin_pwd_input = st.text_input("Enter Admin Management Password", type="password")
            if st.button("Verify & Open Workspace"):
                if admin_pwd_input == db.fetch_admin_config()["password"]:
                    st.session_state.is_admin = True
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid Administrative Password Credential.")

        elif st.session_state.otp_sent:
            otp_token = st.text_input("Enter 6-Digit Code", max_chars=6).strip()
            if st.button("Verify & Login"):
                family_lookup = db.fetch_family_by_email(st.session_state.auth_email)
                if family_lookup:
                    st.session_state.family_id = family_lookup["family_id"]
                    st.session_state.logged_in = True
                    st.rerun()

# -------------------------------------------------------------
# 2. THE MASTER CONTROL PANEL (ADMINISTRATION PORTAL)
# -------------------------------------------------------------
elif st.session_state.is_admin:
    st.sidebar.title("🛡️ Admin Workspace")
    if st.sidebar.button("Secure Log Out"): logout()

    with main_display_viewport:
        admin_tab = st.tabs(["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "⚙️ Settings"])

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
                    st.markdown(f"""
                        <div style='background-color:#f1f3f5; padding:10px 15px; border-radius:6px; margin: 8px 0; font-size:14px; display:inline-block;'>
                            👥 Roster Breakdown: <b>{adm_h_count} members</b>
                        </div>
                    """, unsafe_allow_html=True)
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
            pending_data = db.fetch_pending_approvals()
            for req in pending_data:
                req_id, table, action, payload, target_row_id = req["approval_id"], req["target_table"], req[
                    "action_type"], req["change_payload"] or {}, req["target_id"]
                with st.container(border=True):
                    st.markdown(f"#### ✉️ Request #{req_id}: **{action}** on **{table.upper()}**")
                    st.dataframe(pd.DataFrame([payload]), use_container_width=True, hide_index=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("👍 Approve Change", key=f"appr_{req_id}"):
                            db.process_approval_action(req_id, action, table, payload, target_row_id)
                            # FORCED LIFECYCLE RE-TRIGGER: Reset target verification flag upon new admin approvals
                            if table == "members":
                                m_look = db.supabase.table("members").select("family_id").eq("member_id",
                                                                                             target_row_id).execute()
                                if m_look.data: db.update_family_verification_state(m_look.data[0]["family_id"],
                                                                                    "Pending Update")
                            st.success("Approved!")
                            st.rerun()
                    with c2:
                        if st.button("👎 Reject Change", key=f"rej_{req_id}"):
                            db.reject_pending_approval(req_id)
                            st.rerun()

        with admin_tab[1]:
            st.header("Global Directory Master Tracking View")
            search_q = st.text_input("Type here to search across Head Name, Illam, or Address").strip()
            display_fams = db.fetch_recent_families_global(limit=10) if search_q == "" else db.search_families_global(
                search_q)
            for f in display_fams:
                with st.expander(f"🏡 {f.get('head_of_family')} | ഇല്ലം: {f.get('illam_name')}"):
                    if st.button("🔓 Force Unlock Roster Fields", key=f"force_unl_{f['family_id']}"):
                        db.update_family_verification_state(f['family_id'], "Pending Update")
                        st.rerun()

# -------------------------------------------------------------
# 3. STANDARD USER WORKSPACE (PERMANENTLY EDITABLE ROSTERS)
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
    active_fee = int(admin_cfg["base_family_fee"]) if member_count <= int(admin_cfg["base_member_threshold"]) else int(
        admin_cfg["base_family_fee"]) + ((member_count - int(admin_cfg["base_member_threshold"])) * int(
        admin_cfg["additional_member_fee"]))

    st.title("Yogakshemasabha Household Terminal")

    notification_msg = family_data.get("admin_notification")
    if notification_msg:
        st.info(notification_msg)
        if st.button("Dismiss Notification"): db.clear_user_notification(f_id); st.rerun()

    # Shared Operational States: Profile forms NEVER hard-lock out
    is_disabled = False

    user_tabs = st.tabs(["🏡 Household Profile", "👥 Family Members Roster", "📋 Verify & Settle Dues"])

    # ---- TAB 1: HOUSEHOLD IDENTITY CORE HEADER ----
    with user_tabs[0]:
        st.write("")
        with st.form("edit_family_header_modular_form"):
            h_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)", value=family_data.get('head_of_family', ''))
            h_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)", value=family_data.get('illam_name', ''))
            h_goth = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
            h_addr = st.text_area("മേൽവിലാസം (Address)", value=family_data.get('address', ''))
            if st.form_submit_button("💾 Save Household Information"):
                db.update_family_header(f_id, h_head.strip(), h_illam.strip(), h_goth.strip(), h_addr.strip())
                st.success("Master header variables updated successfully!")
                st.rerun()

    # ---- TAB 2: FUNCTIONAL MEMBERS MANAGEMENT LAYER ----
    with user_tabs[1]:
        st.write("")
        header_address = family_data.get('address', '').strip()

        with st.form("bulk_member_update_modular_form"):
            member_references = []
            if not members_data:
                st.info("ℹ️ No family members mapped yet.")
            else:
                for m in members_data:
                    m_id = m['member_id']
                    with st.container(border=True):
                        st.markdown(f"#### 👤 {m['name']} ({m['relation'] or 'Member'})")
                        c1, c2 = st.columns(2)
                        with c1:
                            m_name = st.text_input("Name *", value=m.get('name', ''), key=f"u_nm_{m_id}")
                            m_rel = st.text_input("Relation *", value=m.get('relation', ''), key=f"u_rl_{m_id}")
                            try:
                                parsed_dob = datetime.datetime.strptime(str(m.get('dob', '1990-01-01')),
                                                                        "%Y-%m-%d").date()
                            except:
                                parsed_dob = datetime.date(1990, 1, 1)
                            m_dob = st.date_input("DOB *", value=parsed_dob, key=f"u_db_{m_id}")
                            m_bg = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS,
                                                index=auth.BLOOD_GROUPS.index(m['blood_group']) if m.get(
                                                    'blood_group') in auth.BLOOD_GROUPS else 0, key=f"u_bg_{m_id}")
                        with c2:
                            m_phone = st.text_input("Phone Number",
                                                    value=str(m.get('phone', '')) if m.get('phone') else '',
                                                    key=f"u_ph_{m_id}")
                            m_email = st.text_input("Email", value=m.get('email', '') or '', key=f"u_em_{m_id}")
                            m_qual = st.text_input("Qualification", value=m.get('qualification', '') or '',
                                                   key=f"u_ql_{m_id}")
                            m_job = st.text_input("Job / Occupation", value=m.get('job', '') or '', key=f"u_jb_{m_id}")

                        st.write("---")
                        m_adhaar = st.text_input("Aadhaar Number",
                                                 value=str(m.get('adhaar', '')) if m.get('adhaar') else '',
                                                 key=f"u_ad_{m_id}")
                        is_same_initial = (
                                    m.get('current_address', '').strip() == header_address or m.get('current_address',
                                                                                                    '').strip() == "")

                        # RADIO RELOCATION INTERFACE TRIGGER
                        m_addr_sel = st.radio("Current Address Context Selector",
                                              options=["Same as Household Address", "Custom Address"],
                                              index=0 if is_same_initial else 1, key=f"u_rad_{m_id}")
                        m_caddr = st.text_area("Enter Custom Current Address",
                                               value=m.get('current_address', '') if not is_same_initial else "",
                                               key=f"u_txa_{m_id}")

                        # INLINE REMOVAL OVERRIDE INTERLOCK
                        m_delete_tick = st.checkbox("🗑️ Request Deletion of this Member Record",
                                                    key=f"u_deltick_{m_id}")

                        member_references.append({
                            "member_id": m_id, "name": m_name, "relation": m_rel, "dob": m_dob,
                            "blood_group": m_bg, "phone": m_phone, "email": m_email,
                            "qualification": m_qual, "job": m_job, "adhaar": m_adhaar,
                            "addr_sel": m_addr_sel, "custom_addr": m_caddr, "should_delete": m_delete_tick
                        })

            st.write("")
            if st.form_submit_button("💾 Process All Roster Modifications / Deletions"):
                for r in member_references:
                    if r["should_delete"]:
                        db.submit_pending_approval("members", "DELETE", st.session_state.auth_email,
                                                   {"name": r['name']}, target_id=r["member_id"])
                    else:
                        is_valid, clean_a = auth.validate_aadhaar(r["adhaar"])
                        if r["name"].strip() == "" or r["relation"].strip() == "":
                            st.error("Mandatory fields are blank.")
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

                # RESET TRIGGER: Instantly drops verification state back upon executing any structural form updates
                db.update_family_verification_state(f_id, "Pending Update")
                st.success("Roster adjustments captured! Verification status refreshed.")
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
                if n_name.strip() == "" or n_rel.strip() == "":
                    st.error("❌ Mandatory parameters missing.")
                else:
                    is_valid, clean_a = auth.validate_aadhaar(n_adhaar)
                    db.submit_pending_approval("members", "INSERT", st.session_state.auth_email, {
                        "family_id": f_id, "name": n_name.strip(), "relation": n_rel.strip(),
                        "dob": n_dob.strftime("%Y-%m-%d"),
                        "blood_group": None if n_blood == 'Not Identified' else n_blood,
                        "phone": n_phone.strip() if n_phone else None, "email": n_email.strip() if n_email else None,
                        "qualification": n_qual.strip() if n_qual else None, "job": n_job.strip() if n_job else None,
                        "adhaar": clean_a if clean_a != "" else None,
                        "current_address": header_address if n_addr_sel == "Same as Household Address" else n_custom_addr.strip()
                    })
                    db.update_family_verification_state(f_id, "Pending Update")
                    st.success("Staged in the admin queue!")
                    st.rerun()

    # ---- TAB 3: HIGHLY INTUITIVE USER-FRIENDLY RECONCILIATION ENGINE ----
    with user_tabs[2]:
        st.write("")
        if not is_audit_window:
            st.info(
                "ℹ️ Institutional dues settlement gates are currently closed outside active verification tracking cycles.")
        else:
            is_user_stuck_in_queue = db.check_if_user_has_pending_requests(st.session_state.auth_email)
            is_awaiting_payment_clearance = (v_status == "Payment Submitted")

            # PROGRESS ROUTE CONTAINER STRIP MAP
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

            # SCREEN LOCK TRIGGERS
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
                st.success("Thank you! Your household profile has been cleared.")
                current_year = datetime.date.today().year
                receipt_template = f"====================================================\n          YOGAKSHEMASABHA CENTRAL TREASURY\n                OFFICIAL PAYMENT RECEIPT\n====================================================\nReceipt Date: {datetime.date.today().strftime('%d-%B-%Y')}\nHousehold Unit: {family_data.get('head_of_family')}\nIllam Name: {family_data.get('illam_name')}\nTotal Members: {member_count} Profile Logs Saved\nAmount Paid: INR {active_fee}.00\nStatus: CLEAR / FULLY VERIFIED CORPS\n===================================================="
                st.code(receipt_template, language="text")
                st.download_button(label="📥 Click Here to Download & Print Receipt", data=receipt_template,
                                   file_name=f"sabha_receipt_{f_id}.txt", mime="text/plain")

            else:
                # STATIC READ-ONLY VERIFICATION VIEW SCREEN
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
                        f"<div style='background-color:#f8f9fa; padding:15px; border-radius:10px; border-left:5px solid #0068c9;'><b>🏘️ Illam Unit Name:</b><br><span style='font-size:18px; font-weight:700;'>{family_data.get('illam_name')}</span></div>",
                        unsafe_allow_html=True)
                with b_col3:
                    st.markdown(
                        f"<div style='background-color:#f8f9fa; padding:15px; border-radius:10px; border-left:5px solid #29b6f6;'><b>👥 Registered Headcount:</b><br><span style='font-size:18px; font-weight:700;'>{member_count} Members</span></div>",
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
                        st.success("Roster verified! Gateway checkout unlocked below.")
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
                                st.warning("⚠️ Official QR asset un-uploaded.")
                            st.markdown(
                                "<p style='text-align:center; font-size:12px; color:#6c757d; margin-top:5px;'>Open Google Pay, PhonePe, Bhim, or PayTM on your mobile phone and hold it up to scan this QR box.</p>",
                                unsafe_allow_html=True)

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
                        st.markdown("#### ✍️ After paying, paste your receipt number below:")
                        st.write(
                            "Once your mobile payment goes through successfully, please type that 12-digit transaction number into this box below to let the treasurer clear your account:")

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