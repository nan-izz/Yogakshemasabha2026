import streamlit as st
import os
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
    if cleaned == "" or cleaned.lower() == "none" or cleaned.lower() == "null":
        return True, ""  
    if len(cleaned) == 12 and cleaned.isdigit():
        return True, cleaned
    return False, None

# Initialize Session State
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

def logout():
    st.session_state.logged_in = False
    st.session_state.family_id = None
    st.session_state.auth_email = None
    st.session_state.otp_sent = False
    st.session_state.login_mode = "email"
    st.rerun()

# -------------------------------------------------------------
# 1. LANDING PAGE / LOGIN
# -------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("Yogakshemasabha Portal")

    if st.session_state.login_mode == "email":
        st.subheader("Login with your registered Household Email")
        if not st.session_state.otp_sent:
            input_email = st.text_input("Family Email Address").strip().lower()
            if st.button("Send Verification OTP"):
                if "@" not in input_email or "." not in input_email: 
                    st.error("Please enter a valid email address.")
                else:
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
                        st.error("Email not found in database records. Use Onboarding option below if first time.")
            st.write("---")
            if st.button("Forgot / No Email ID Registered? Click here to verify via Family Details"):
                st.session_state.login_mode = "backdoor"
                st.rerun()
        else:
            st.info(f"Logging in as: **{st.session_state.auth_email}**")
            otp_token = st.text_input("Enter 6-Digit Code", max_chars=6).strip()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify & Login"):
                    try:
                        family_lookup = supabase.table("families").select("family_id").eq("email_id", st.session_state.auth_email).execute()
                        if family_lookup.data:
                            st.session_state.family_id = family_lookup.data[0]["family_id"]
                            st.session_state.logged_in = True
                            st.rerun()
                    except:
                        st.error("Invalid token. Please check your email again.")
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
                if found.get("email_id"):
                    st.error(f"Access Restricted! This profile already has a registered email ({found['email_id']}).")
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
# 2. APPLICATION DASHBOARD (CRUD ENGINE)
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"):
        logout()

    st.title("Yogakshemasabha Portal Dashboard")
    family_data = supabase.table("families").select("*").eq("family_id", f_id).execute().data[0]
    header_address = family_data.get('address', '').strip()

    # ---- HOUSEHOLD INFORMATION HEADER ----
    st.header("🏠 Household Information")
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
            st.success("Household updates committed!")
            st.rerun()

    # ---- EMAIL INTERCEPT ----
    current_email = family_data.get('email_id')
    if not current_email:
        with st.status("📧 Phase 2 Security Setup Required", expanded=True):
            new_email = st.text_input("Enter Family Email Address").strip().lower()
            if st.button("Save & Link Email"):
                if "@" not in new_email or "." not in new_email: st.error("Invalid email.")
                else:
                    try:
                        supabase.table("families").update({"email_id": new_email}).eq("family_id", f_id).execute()
                        st.success("Email linked!")
                        st.rerun()
                    except: st.error("Email already in use by another household.")
    else:
        st.info(f"🔒 Registered Login Identifier: **{current_email}**")

    # ---- EDIT/DELETE EXISTING MEMBERS ----
    st.header("👥 Registered Family Members")
    members_data = supabase.table("members").select("*").eq("family_id", f_id).order("member_id").execute().data
    
    if members_data:
        for member in members_data:
            m_id = member['member_id']
            
            with st.expander(f"👤 {member['name']} ({member['relation'] or 'Member'})", expanded=False):
                # Using st.container avoids the "Missing Submit Button" warning entirely
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
                    
                    # Inside container radio logic triggers clean, dynamic, warning-free updates
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
                    
                    # Regular action buttons
                    if st.button(f"Save Profile Changes for {member['name']}", key=f"save_btn_{m_id}"):
                        if m_name.strip() == "" or m_relation.strip() == "" or m_dob.strip() == "":
                            st.error("❌ Name, Relation, and Date of Birth (DOB) are mandatory fields!")
                        else:
                            is_valid_adhaar, cleaned_adhaar = validate_aadhaar(m_adhaar)
                            
                            if not is_valid_adhaar:
                                st.error("❌ Invalid Aadhaar Number! It must be exactly 12 numeric digits or left completely blank.")
                            else:
                                final_addr = header_address if m_addr_selection == "Same as above" else m_curr_addr.strip()
                                final_bg = None if m_blood == 'Not Identified' else m_blood
                                
                                supabase.table("members").update({
                                    "name": m_name.strip(),
                                    "relation": m_relation.strip(),
                                    "dob": m_dob.strip(),
                                    "blood_group": final_bg,
                                    "phone": m_phone.strip(),
                                    "email": m_email.strip(),
                                    "qualification": m_qual.strip(),
                                    "job": m_job.strip(),
                                    "adhaar": cleaned_adhaar if cleaned_adhaar != "" else None,
                                    "current_address": final_addr
                                }).eq("member_id", m_id).execute()
                                st.success("Profile saved successfully!")
                                st.rerun()
                
                if st.button(f"❌ Delete {member['name']}", key=f"del_btn_{m_id}"):
                    supabase.table("members").delete().eq("member_id", m_id).execute()
                    st.warning("Member has been removed.")
                    st.rerun()
    else:
        st.info("No members currently mapped to this profile.")

    # ---- ADD NEW MEMBER FORM ----
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
            
            new_addr_selection = st.radio(
                "Current Address Selection", 
                options=["Same as above", "Not same as above"], 
                index=0,
                key="new_member_addr_radio"
            )
            
            new_custom_addr = ""
            if new_addr_selection == "Not same as above":
                new_custom_addr = st.text_area("Enter Custom Current Address", value="", key="new_member_custom_addr")
            
            if st.button("Add Member", key="new_member_submit"):
                if new_name.strip() == "" or new_relation.strip() == "" or new_dob.strip() == "":
                    st.error("❌ Name, Relation, and Date of Birth (DOB) are mandatory fields!")
                else:
                    is_valid_adhaar, cleaned_adhaar = validate_aadhaar(new_adhaar)
                    
                    if not is_valid_adhaar:
                        st.error("❌ Invalid Aadhaar Number! It must be exactly 12 numeric digits or left completely blank.")
                    else:
                        final_addr = header_address if new_addr_selection == "Same as above" else new_custom_addr.strip()
                        final_bg = None if new_blood == 'Not Identified' else new_blood
                        
                        supabase.table("members").insert({
                            "family_id": f_id,
                            "name": new_name.strip(),
                            "relation": new_relation.strip(),
                            "dob": new_dob.strip(),
                            "blood_group": final_bg,
                            "phone": new_phone.strip(),
                            "email": new_email.strip(),
                            "qualification": new_qual.strip(),
                            "job": new_job.strip(),
                            "adhaar": cleaned_adhaar if cleaned_adhaar != "" else None,
                            "current_address": final_addr
                        }).execute()
                        
                        st.success(f"{new_name.strip()} added successfully!")
                        st.rerun()
