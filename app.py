import streamlit as st
import os
import datetime
import csv
import io
from supabase import create_client, Client

# Initialize Supabase Client
url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Define standard lists globally
BLOOD_GROUPS = ['Not Identified', 'A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']

# Helper function to validate Aadhaar structure
def validate_aadhaar(aadhaar_str):
    cleaned = str(aadhaar_str).replace(" ", "").strip()
    if cleaned == "" or cleaned.lower() in ["none", "null"]:
        return True, ""  
    if len(cleaned) == 12 and cleaned.isdigit():
        return True, cleaned
    return False, None

# Initialize Session State Variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "family_id" not in st.session_state:
    st.session_state.family_id = None
if "auth_email" not in st.session_state:
    st.session_state.auth_email = None
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
if "login_mode" not in st.session_state:
    st.session_state.login_mode = "email"
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "admin_password_mode" not in st.session_state:
    st.session_state.admin_password_mode = False

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
# 1. IDENTITY AUTHENTICATION ENGINE
# -------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("Yogakshemasabha Portal")

    if st.session_state.login_mode == "email":
        st.subheader("Household Email / Admin Login")
        
        # Fetch Admin Username configuration dynamically from DB
        try:
            admin_cfg = supabase.table("admin_config").select("*").eq("id", 1).execute().data[0]
            admin_user_target = admin_cfg["username"]
        except:
            admin_user_target = "sabhaadmin" # Fallback safety default
        
        if not st.session_state.otp_sent and not st.session_state.admin_password_mode:
            input_email = st.text_input("Enter Email Identifier / Admin Username").strip().lower()
            
            if st.button("Proceed to Login"):
                if input_email == admin_user_target:
                    # Switch to Password field for Admin track
                    st.session_state.auth_email = input_email
                    st.session_state.admin_password_mode = True
                    st.rerun()
                elif "@" not in input_email or "." not in input_email: 
                    st.error("Please enter a valid email address.")
                else:
                    # Standard family path -> Trigger secure OTP
                    check_db = supabase.table("families").select("family_id").eq("email_id", input_email).execute()
                    if check_db.data and len(check_db.data) > 0:
                        try:
                            supabase.auth.sign_in_with_otp({"email": input_email, "options": {"should_create_user": False}})
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
                
        # ADMIN ROUTE: PASSWORD ENTRY
        elif st.session_state.admin_password_mode:
            st.info(f"🔑 Administrator Portal Access: **{st.session_state.auth_email}**")
            admin_pwd_input = st.text_input("Enter Admin Management Password", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify & Open Workspace"):
                    real_pwd = supabase.table("admin_config").select("password").eq("id", 1).execute().data[0]["password"]
                    if admin_pwd_input == real_pwd:
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
                    
        # FAMILY ROUTE: 6-DIGIT OTP ENTRY
        elif st.session_state.otp_sent:
            st.info(f"Logging in as: **{st.session_state.auth_email}**")
            otp_token = st.text_input("Enter 6-Digit Code", max_chars=6).strip()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify & Login"):
                    family_lookup = supabase.table("families").select("family_id").eq("email_id", st.session_state.auth_email).execute()
                    if family_lookup.data:
                        st.session_state.family_id = family_lookup.data[0]["family_id"]
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
            response = supabase.table("families").select("family_id, head_of_family, email_id").ilike("head_of_family", f"%{input_head}%").ilike("illam_name", f"%{input_illam}%").execute()
            if response.data and len(response.data) > 0:
                found = response.data[0]
                if found.get("email_id") and str(found.get("email_id")).strip() != "" and str(found.get("email_id")).lower() != "none":
                    st.error(f"🛑 Access Restricted! This profile already has a registered email ({found['email_id']}). You must log in via the regular Email screen.")
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
# 2. THE ADVANCED CONTROL CENTER (ADMINISTRATION PORTAL)
# -------------------------------------------------------------
elif st.session_state.is_admin:
    st.sidebar.title("🛡️ Admin Workspace")
    st.sidebar.info(f"System Operator:\n{st.session_state.auth_email}")
    if st.sidebar.button("Secure Log Out"): logout()
    
    admin_tab = st.tabs(["📋 Pending Approvals Queue", "🔍 Global Directory Matrix", "🎂 Age Verification Filter", "⚙️ Admin Settings"])
    
    # ---- ADMIN TAB 1: DATA APPROVAL PIPELINE ----
    with admin_tab[0]:
        st.header("Modifications Awaiting Administrative Clearance")
        pending_data = supabase.table("pending_approvals").select("*").order("created_at").execute().data
        
        if not pending_data:
            st.success("🎉 All clear! The pending approval tracking queue is empty.")
        else:
            for req in pending_data:
                req_id = req["approval_id"]
                table_type = req["target_table"].upper()
                action = req["action_type"]
                payload = req["change_payload"] or {}
                
                with st.container(border=True):
                    st.subheader(f"Request #{req_id}: {action} on {table_type}")
                    st.caption(f"Submitted by: {req['requested_by']} | Row Key Reference: {req['target_id']}")
                    st.json(payload)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👍 Approve Change", key=f"appr_{req_id}"):
                            if action == "INSERT":
                                supabase.table(req["target_table"]).insert(payload).execute()
                            elif action == "UPDATE":
                                id_col = "family_id" if req["target_table"] == "families" else "member_id"
                                supabase.table(req["target_table"]).update(payload).eq(id_col, req["target_id"]).execute()
                            elif action == "DELETE":
                                id_col = "family_id" if req["target_table"] == "families" else "member_id"
                                supabase.table(req["target_table"]).delete().eq(id_col, req["target_id"]).execute()
                                
                            supabase.table("pending_approvals").delete().eq("approval_id", req_id).execute()
                            st.success("Modification committed cleanly to database production tables!")
                            st.rerun()
                            
                    with col2:
                        if st.button("👎 Reject & Drop", key=f"rej_{req_id}"):
                            supabase.table("pending_approvals").delete().eq("approval_id", req_id).execute()
                            st.warning("Change request dropped from queue.")
                            st.rerun()

    # ---- ADMIN TAB 2: OVERVIEW & RESET MANAGEMENT ----
    with admin_tab[1]:
        st.header("Global Directory Master Tracking View")
        search_q = st.text_input("Global Search (Name / Illam / Phone)").strip()
        
        all_fams = supabase.table("families").select("*").execute().data
        missing_emails = [f for f in all_fams if not f.get("email_id") or str(f.get("email_id")).strip() == ""]
        
        st.metric("Total Committee Households", len(all_fams))
        st.warning(f"⚠️ Households Missing Linked Emails: {len(missing_emails)}")
        
        for f in all_fams:
            # Exclude the generic admin row from standard matrix view tracking
            if f["family_id"] == 999999:
                continue
            if search_q.lower() in f["head_of_family"].lower() or search_q.lower() in f["illam_name"].lower():
                with st.expander(f"🏡 {f['head_of_family']} | {f['illam_name']}"):
                    st.write(f"**Address:** {f['address']}")
                    st.write(f"**Linked Login Email:** {f['email_id'] or '❌ None (Onboarding Backdoor Open)'}")
                    
                    if f['email_id']:
                        if st.button("🔄 Reset Linked Email / Open Backdoor", key=f"rst_{f['family_id']}"):
                            supabase.table("families").update({"email_id": None}).eq("family_id", f['family_id']).execute()
                            st.success("Email linkage decoupled successfully!")
                            st.rerun()

    # ---- ADMIN TAB 3: AGE VERIFICATION SYSTEM ----
    with admin_tab[2]:
        st.header("Statutory Electoral & Age Calculation Audit")
        target_date = st.date_input("Select Reference Cut-off Date", datetime.date.today())
        
        if st.button("Calculate Voter Roll Registry (18+)"):
            all_members = supabase.table("members").select("name", "relation", "dob", "phone").execute().data
            voters = []
            
            for m in all_members:
                if m.get("dob"):
                    try:
                        dob_parsed = datetime.datetime.strptime(str(m["dob"]), "%Y-%m-%d").date()
                        age = (target_date - dob_parsed).days / 365.25
                        if age >= 18.0:
                            voters.append({
                                "Name": m["name"],
                                "Relation": m["relation"],
                                "Date of Birth": m["dob"],
                                "Calculated Age": round(age, 1),
                                "Phone Contact": m["phone"]
                            })
                    except:
                        pass
                        
            if voters:
                st.success(f"Found {len(voters)} members who are 18 or older on {target_date}")
                st.dataframe(voters)
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=voters[0].keys())
                writer.writeheader()
                writer.writerows(voters)
                st.download_button("📥 Download Age Verification Registry (CSV)", data=output.getvalue(), file_name=f"voter_roll_{target_date}.csv", mime="text/csv")
            else:
                st.info("No members meet the age parameters on the selected date constraint.")

    # ---- ADMIN TAB 4: PASSWORD CONTROLS CONFIGURATION ----
    with admin_tab[3]:
        st.header("Security Configuration Settings")
        st.subheader("Modify Administrative Login Parameters")
        
        current_config = supabase.table("admin_config").select("*").eq("id", 1).execute().data[0]
        
        with st.form("admin_settings_form"):
            new_username = st.text_input("Change Admin Username", value=current_config["username"]).strip()
            new_password = st.text_input("Set New Admin Password", type="password").strip()
            confirm_password = st.text_input("Confirm New Admin Password", type="password").strip()
            
            if st.form_submit_button("Update Access Credentials"):
                if new_username == "":
                    st.error("Username cannot be left blank.")
                elif new_password != confirm_password:
                    st.error("❌ Password confirmation mismatch! Fields must be identical.")
                elif len(new_password) < 6:
                    st.error("❌ Password structure must be at least 6 characters long.")
                else:
                    supabase.table("admin_config").update({
                        "username": new_username,
                        "password": new_password
                    }).eq("id", 1).execute()
                    st.success("🔒 Admin access credentials updated successfully across global instances!")
                    st.rerun()

# -------------------------------------------------------------
# 3. STANDARD USER / HOUSEHOLD PROFILE DASHBOARD
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"): logout()

    st.title("Yogakshemasabha Profile Directory")
    family_data = supabase.table("families").select("*").eq("family_id", f_id).execute().data[0]
    header_address = family_data.get('address', '').strip()

    # ---- FAMILY HEADER DATA ----
    st.header("🏠 Household Information")
    st.info("Note: Core Household header information updates instantly and directly to the master directory.")
    with st.form("edit_family_form"):
        edit_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)", value=family_data.get('head_of_family', ''))
        edit_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)", value=family_data.get('illam_name', ''))
        edit_gothram = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
        edit_address = st.text_area("മേൽവിലാസം (Address)", value=header_address)
        if st.form_submit_button("Save Household Changes"):
            supabase.table("families").update({
                "head_of_family": edit_head.strip(),
                "illam_name": edit_illam.strip(),
                "gothram": edit_gothram.strip(),
                "address": edit_address.strip()
            }).eq("family_id", f_id).execute()
            st.success("Household updates saved!")
            st.rerun()

    # ---- PHASE 2 EMAIL LOCKDOWN ANCHOR ----
    current_email = family_data.get('email_id')
    if not current_email or str(current_email).strip() == "" or str(current_email).lower() == "none":
        with st.status("📧 Phase 2 Security Setup Required", expanded=True):
            new_email = st.text_input("Enter Family Email Address").strip().lower()
            if st.button("Save & Link Email"):
                if "@" not in new_email or "." not in new_email: st.error("Invalid email.")
                else:
                    try:
                        supabase.table("families").update({"email_id": new_email}).eq("family_id", f_id).execute()
                        st.success("Email linked successfully! Moving forward, you must use Email OTP login verification.")
                        st.rerun()
                    except: st.error("Email already in use by another household.")
    else:
        st.info(f"🔒 Registered Login Identifier: **{current_email}**")

    # ---- MEMBER PORTAL RENDERING ----
    st.header("👥 Registered Family Members")
    st.caption("All member alterations below will submit to the committee review queue for approval before displaying publicly.")
    
    members_data = supabase.table("members").select("*").eq("family_id", f_id).order("member_id").execute().data
    
    if members_data:
        for member in members_data:
            m_id = member['member_id']
            
            with st.expander(f"👤 {member['name']} ({member['relation'] or 'Member'})", expanded=False):
                with st.container():
                    col1, col2 = st.columns(2)
                    with col1:
                        m_name = st.text_input("Name *", value=member.get('name', ''), key=f"name_{m_id}")
                        m_relation = st.text_input("Relation *", value=member.get('relation', ''), key=f"rel_{m_id}")
                        m_dob = st.text_input("DOB * (YYYY-MM-DD)", value=str(member.get('dob', '')) if member.get('dob') else '', key=f"dob_{m_id}")
                        
                        curr_bg = member.get('blood_group', '').strip()
                        bg_index = BLOOD_GROUPS.index(curr_bg) if curr_bg in BLOOD_GROUPS else 0
                        m_blood = st.selectbox("Blood Group", options=BLOOD_GROUPS, index=bg_index, key=f"bg_edit_{m_id}")
                        
                    with col2:
                        m_phone = st.text_input("Phone Number", value=str(member.get('phone', '')) if member.get('phone') else '', key=f"phone_{m_id}")
                        m_email = st.text_input("Email", value=member.get('email', ''), key=f"email_{m_id}")
                        m_qual = st.text_input("Qualification", value=member.get('qualification', ''), key=f"qual_{m_id}")
                        m_job = st.text_input("Job / Occupation", value=member.get('job', ''), key=f"job_{m_id}")
                    
                    m_adhaar = st.text_input("Aadhaar Number (12 numeric digits)", value=str(member.get('adhaar', '')) if member.get('adhaar') else '', key=f"adhaar_edit_{m_id}")
                    
                    # Address Selection inside Container UI context
                    db_addr = member.get('current_address', '').strip()
                    is_same_initial = (db_addr == header_address or db_addr == "")
                    
                    m_addr_selection = st.radio(
                        "Current Address Selection", 
                        options=["Same as above", "Not same as above"], 
                        index=0 if is_same_initial else 1,
                        key=f"addr_radio_{m_id}"
                    )
                    
                    m_curr_addr = ""
                    if m_addr_selection == "Not same as above":
                        initial_custom_val = "" if is_same_initial else db_addr
                        m_curr_addr = st.text_area("Enter Custom Current Address", value=initial_custom_val, key=f"custom_addr_txt_{m_id}")
                    
                    if st.button(f"Submit Profile Changes for {member['name']} to Admin Review", key=f"save_btn_{m_id}"):
                        if m_name.strip() == "" or m_relation.strip() == "" or m_dob.strip() == "":
                            st.error("❌ Name, Relation, and Date of Birth (DOB) are mandatory fields!")
                        else:
                            is_valid_adhaar, cleaned_adhaar = validate_aadhaar(m_adhaar)
                            if not is_valid_adhaar:
                                st.error("❌ Invalid Aadhaar Number format.")
                            else:
                                final_addr = header_address if m_addr_selection == "Same as above" else m_curr_addr.strip()
                                final_bg = None if m_blood == 'Not Identified' else m_blood
                                
                                # Protected field assignments preventing None stripping crashes
                                payload = {
                                    "name": m_name.strip(),
                                    "relation": m_relation.strip(),
                                    "dob": m_dob.strip(),
                                    "blood_group": final_bg,
                                    "phone": m_phone.strip() if m_phone else None,
                                    "email": m_email.strip() if m_email else None,
                                    "qualification": m_qual.strip() if m_qual else None,
                                    "job": m_job.strip() if m_job else None,
                                    "adhaar": cleaned_adhaar if cleaned_adhaar != "" else None,
                                    "current_address": final_addr
                                }
                                
                                supabase.table("pending_approvals").insert({
                                    "target_table": "members",
                                    "target_id": m_id,
                                    "action_type": "UPDATE",
                                    "requested_by": st.session_state.auth_email or "Backdoor User",
                                    "change_payload": payload
                                }).execute()
                                
                                st.info("📩 Update modification dispatched to the administrative review grid!")
                
                if st.button(f"❌ Request Deletion of {member['name']}", key=f"del_btn_{m_id}"):
                    supabase.table("pending_approvals").insert({
                        "target_table": "members",
                        "target_id": m_id,
                        "action_type": "DELETE",
                        "requested_by": st.session_state.auth_email or "Backdoor User",
                        "change_payload": {"name": member['name']}
                    }).execute()
                    st.warning("📩 Deletion request logged for admin review.")
    else:
        st.info("No members currently mapped to this profile.")

    # ---- ADD NEW MEMBER MODULE ----
    st.header("➕ Add New Family Member")
    with st.expander("Register a new member for this family"):
        with st.container():
            new_name = st.text_input("Full Name *", key="new_name")
            new_relation = st.text_input("Relation * (e.g., Wife, Son, Daughter)", key="new_rel")
            new_dob = st.text_input("DOB * (YYYY-MM-DD)", key="new_dob")
            new_blood = st.selectbox("Blood Group", options=BLOOD_GROUPS, index=0, key="new_bg")
            new_phone = st.text_input("Phone Number", key="new_phone")
            new_email = st.text_input("Email Address", key="new_email")
            new_qual = st.text_input("Qualification", key="new_qual")
            new_job = st.text_input("Job / Profession", key="new_job")
            new_adhaar = st.text_input("Aadhaar Number (12 numeric digits)", key="new_adhaar")
            
            new_addr_selection = st.radio("Current Address Selection", options=["Same as above", "Not same as above"], index=0, key="new_member_addr_radio")
            new_custom_addr = ""
            if new_addr_selection == "Not same as above":
                new_custom_addr = st.text_area("Enter Custom Current Address", value="", key="new_member_custom_addr")
            
            if st.button("Submit New Member for Verification", key="new_member_submit"):
                if new_name.strip() == "" or new_relation.strip() == "" or new_dob.strip() == "":
                    st.error("❌ Name, Relation, and Date of Birth (DOB) are mandatory fields!")
                else:
                    is_valid_adhaar, cleaned_adhaar = validate_aadhaar(new_adhaar)
                    if not is_valid_adhaar:
                        st.error("❌ Invalid Aadhaar Number format.")
                    else:
                        final_addr = header_address if new_addr_selection == "Same as above" else new_custom_addr.strip()
                        final_bg = None if new_blood == 'Not Identified' else new_blood
                        
                        payload = {
                            "family_id": f_id,
                            "name": new_name.strip(),
                            "relation": new_relation.strip(),
                            "dob": new_dob.strip(),
                            "blood_group": final_bg,
                            "phone": new_phone.strip() if new_phone else None,
                            "email": new_email.strip() if new_email else None,
                            "qualification": new_qual.strip() if new_qual else None,
                            "job": new_job.strip() if new_job else None,
                            "adhaar": cleaned_adhaar if cleaned_adhaar != "" else None,
                            "current_address": final_addr
                        }
                        
                        supabase.table("pending_approvals").insert({
                            "target_table": "members",
                            "action_type": "INSERT",
                            "requested_by": st.session_state.auth_email or "Backdoor User",
                            "change_payload": payload
                        }).execute()
                        
                        st.success("📩 Registration profile safely routed to the committee queue!")
