import streamlit as st
import datetime
import csv
import io

# Import modular custom logic engines
import database as db
import auth

st.set_page_index = "wide"

# Initialize Session State Variables
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "family_id" not in st.session_state: st.session_state.family_id = None
if "auth_email" not in st.session_state: st.session_state.auth_email = None
if "otp_sent" not in st.session_state: st.session_state.otp_sent = False
if "login_mode" not in st.session_state: st.session_state.login_mode = "email"
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "admin_password_mode" not in st.session_state: st.session_state.admin_password_mode = False


def logout():
    st.session_state.logged_in = False
    st.session_state.family_id = None
    st.session_state.auth_email = None
    st.session_state.otp_sent = False
    st.session_state.login_mode = "email"
    st.session_state.is_admin = False
    st.session_state.admin_password_mode = False
    st.rerun()


# -------------------------------------------------------------
# APPLICATION ENTRY LAYER (LOGINS & IDENTITIES)
# -------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("Yogakshemasabha Portal")

    if st.session_state.login_mode == "email":
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
            if st.button("Forgot / No Email ID Registered? Click here to verify via Family Details"):
                st.session_state.login_mode = "backdoor"
                st.rerun()

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
# PRODUCTION MANAGEMENT LAYER (THE ADMIN ENVIRONMENT)
# -------------------------------------------------------------
elif st.session_state.is_admin:
    st.sidebar.title("🛡️ Admin Workspace")
    if st.sidebar.button("Secure Log Out"): logout()

    admin_tab = st.tabs(
        ["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "🎂 Age Verification Filter", "⚙️ Admin Settings"])

    with admin_tab[0]:
        st.header("Modifications Awaiting Administrative Clearance")
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

    with admin_tab[1]:
        st.header("Global Directory Master Tracking View")
        search_q = st.text_input("Search households across Head Name, Illam, Phone or Address").strip().lower()
        all_fams = db.fetch_all_families_global()
        missing_emails = [f for f in all_fams if not f.get("email_id") or str(f.get("email_id")).strip() == ""]

        st.metric("Total Active Households", len(all_fams) - 1 if len(all_fams) > 0 else 0)
        st.warning(f"⚠️ Profiles Missing Linked Login Emails: {len(missing_emails)}")

        for f in all_fams:
            if f["family_id"] == 999999: continue
            if search_q == "" or (search_q in (f.get("head_of_family") or "").lower() or search_q in (
                    f.get("illam_name") or "").lower() or search_q in (f.get("address") or "").lower()):
                with st.expander(f"🏡 {f.get('head_of_family')} | ഇല്ലം: {f.get('illam_name')}"):

                    if not f.get("email_id"):
                        pre_reg_email = st.text_input("Enter Email to bind to this household profile",
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
                        if st.button("🔄 Reset Linked Email / Unlock Fallback Backdoor", key=f"rst_{f['family_id']}"):
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
                                ma_dob = st.text_input("DOB (YYYY-MM-DD)", value=str(m["dob"]) if m.get("dob") else "")
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

    with admin_tab[2]:
        st.header("Statutory Electoral & Age Calculation Audit")
        target_date = st.date_input("Select Reference Cut-off Date", datetime.date.today())

        if st.button("Calculate Voter Roll Registry (18+)"):
            all_members = db.fetch_all_members_global()
            voters = auth.calculate_voter_roll(all_members, all_fams, target_date)

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

    with admin_tab[3]:
        st.header("Security Configuration Settings")
        current_config = db.fetch_admin_config()
        with st.form("admin_settings_form"):
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
# STANDARD USER PORTAL DASHBOARD (RE-ROUTING FIELDS VIA PAYLOAD QUEUES)
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"): logout()

    st.title("Yogakshemasabha Profile Directory")
    family_data = db.fetch_single_family(f_id)
    header_address = family_data.get('address', '').strip()

    st.header("🏠 Household Information")
    with st.form("edit_family_form"):
        edit_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)", value=family_data.get('head_of_family', ''))
        edit_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)", value=family_data.get('illam_name', ''))
        edit_gothram = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
        edit_address = st.text_area("മേൽവിലാസം (Address)", value=header_address)
        if st.form_submit_button("Save Household Changes"):
            db.update_family_header(f_id, edit_head, edit_illam, edit_gothram, edit_address)
            st.success("Household updates saved!")
            st.rerun()

    current_email = family_data.get('email_id')
    if not current_email or str(current_email).strip() == "" or str(current_email).lower() == "none":
        with st.status("📧 Phase 2 Security Setup Required", expanded=True):
            new_email = st.text_input("Enter Family Email Address").strip().lower()
            if st.button("Save & Link Email"):
                if "@" not in new_email or "." not in new_email:
                    st.error("Invalid email.")
                else:
                    try:
                        db.link_family_email(f_id, new_email)
                        st.success("Email linked successfully!")
                        st.rerun()
                    except:
                        st.error("Email already in use by another household.")
    else:
        st.info(f"🔒 Registered Login Identifier: **{current_email}**")

    st.header("👥 Registered Family Members")
    st.caption(
        "All member alterations below will submit to the committee review queue for approval before displaying publicly.")
    members_data = db.fetch_family_members(f_id)

    if members_data:
        for member in members_data:
            m_id = member['member_id']
            with st.expander(f"👤 {member['name']} ({member['relation'] or 'Member'})", expanded=False):
                with st.container():
                    col1, col2 = st.columns(2)
                    with col1:
                        m_name = st.text_input("Name *", value=member.get('name', ''), key=f"name_{m_id}")
                        m_relation = st.text_input("Relation *", value=member.get('relation', ''), key=f"rel_{m_id}")
                        m_dob = st.text_input("DOB * (YYYY-MM-DD)",
                                              value=str(member.get('dob', '')) if member.get('dob') else '',
                                              key=f"dob_{m_id}")
                        bg_index = auth.BLOOD_GROUPS.index(member['blood_group']) if member.get(
                            'blood_group') in auth.BLOOD_GROUPS else 0
                        m_blood = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS, index=bg_index,
                                               key=f"bg_edit_{m_id}")
                    with col2:
                        m_phone = st.text_input("Phone Number",
                                                value=str(member.get('phone', '')) if member.get('phone') else '',
                                                key=f"phone_{m_id}")
                        m_email = st.text_input("Email", value=member.get('email', ''), key=f"email_{m_id}")
                        m_qual = st.text_input("Qualification", value=member.get('qualification', ''),
                                               key=f"qual_{m_id}")
                        m_job = st.text_input("Job / Occupation", value=member.get('job', ''), key=f"job_{m_id}")

                    m_adhaar = st.text_input("Aadhaar Number (12 numeric digits)",
                                             value=str(member.get('adhaar', '')) if member.get('adhaar') else '',
                                             key=f"adhaar_edit_{m_id}")
                    is_same_initial = (member.get('current_address', '').strip() == header_address or member.get(
                        'current_address', '').strip() == "")
                    m_addr_selection = st.radio("Current Address Selection",
                                                options=["Same as above", "Not same as above"],
                                                index=0 if is_same_initial else 1, key=f"addr_radio_{m_id}")

                    m_curr_addr = ""
                    if m_addr_selection == "Not same as above":
                        m_curr_addr = st.text_area("Enter Custom Current Address",
                                                   value="" if is_same_initial else member.get('current_address', ''),
                                                   key=f"custom_addr_txt_{m_id}")

                    if st.button(f"Submit Profile Changes for {member['name']} to Admin Review",
                                 key=f"save_btn_{m_id}"):
                        if m_name.strip() == "" or m_relation.strip() == "" or m_dob.strip() == "":
                            st.error("❌ Required inputs are blank!")
                        else:
                            is_valid, clean_a = auth.validate_aadhaar(m_adhaar)
                            if not is_valid:
                                st.error("❌ Invalid Aadhaar.")
                            else:
                                db.submit_pending_approval("members", "UPDATE", st.session_state.auth_email, {
                                    "name": m_name.strip(), "relation": m_relation.strip(), "dob": m_dob.strip(),
                                    "blood_group": None if m_blood == 'Not Identified' else m_blood,
                                    "phone": m_phone.strip() if m_phone else None,
                                    "email": m_email.strip() if m_email else None,
                                    "qualification": m_qual.strip() if m_qual else None,
                                    "job": m_job.strip() if m_job else None,
                                    "adhaar": clean_a if clean_a != "" else None,
                                    "current_address": header_address if m_addr_selection == "Same as above" else m_curr_addr.strip()
                                }, target_id=m_id)
                                st.info("📩 Dispatched to administrative queue layout!")

                if st.button(f"❌ Request Deletion of {member['name']}", key=f"del_btn_{m_id}"):
                    db.submit_pending_approval("members", "DELETE", st.session_state.auth_email,
                                               {"name": member['name']}, target_id=m_id)
                    st.warning("📩 Deletion flag queued for audit review.")
    else:
        st.info("No members mapped to this profile.")

    st.header("➕ Add New Family Member")
    with st.expander("Register a new member for this family"):
        with st.container():
            new_name = st.text_input("Full Name *", key="new_name")
            new_relation = st.text_input("Relation * (e.g., Wife, Son)", key="new_rel")
            new_dob = st.text_input("DOB * (YYYY-MM-DD)", key="new_dob")
            new_blood = st.selectbox("Blood Group", options=auth.BLOOD_GROUPS, index=0, key="new_bg")
            new_phone = st.text_input("Phone Number", key="new_phone")
            new_email = st.text_input("Email Address", key="new_email")
            new_qual = st.text_input("Qualification", key="new_qual")
            new_job = st.text_input("Job / Profession", key="new_job")
            new_adhaar = st.text_input("Aadhaar Number (12 numeric digits)", key="new_adhaar")
            new_addr_selection = st.radio("Current Address Selection", options=["Same as above", "Not same as above"],
                                          index=0, key="new_member_addr_radio")
            new_custom_addr = st.text_area("Enter Custom Current Address", value="",
                                           key="new_member_custom_addr") if new_addr_selection == "Not same as above" else ""

            if st.button("Submit New Member for Verification", key="new_member_submit"):
                if new_name.strip() == "" or new_relation.strip() == "" or new_dob.strip() == "":
                    st.error("❌ Mandatory parameters missing.")
                else:
                    is_valid, clean_a = auth.validate_aadhaar(new_adhaar)
                    if not is_valid:
                        st.error("❌ Invalid Aadhaar Number format.")
                    else:
                        db.submit_pending_approval("members", "INSERT", st.session_state.auth_email, {
                            "family_id": f_id, "name": new_name.strip(), "relation": new_relation.strip(),
                            "dob": new_dob.strip(), "blood_group": None if new_blood == 'Not Identified' else new_blood,
                            "phone": new_phone.strip() if new_phone else None,
                            "email": new_email.strip() if new_email else None,
                            "qualification": new_qual.strip() if new_qual else None,
                            "job": new_job.strip() if new_job else None,
                            "adhaar": clean_a if clean_a != "" else None,
                            "current_address": header_address if new_addr_selection == "Same as above" else new_custom_addr.strip()
                        })
                        st.success("📩 Registration safely routed to the committee queue!")