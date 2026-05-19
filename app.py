import streamlit as st
import os
from supabase import create_client, Client

# Initialize Supabase Client
url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

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
    st.session_state.login_mode = "email"  # 'email' or 'backdoor'

def logout():
    st.session_state.logged_in = False
    st.session_state.family_id = None
    st.session_state.auth_email = None
    st.session_state.otp_sent = False
    st.session_state.login_mode = "email"
    st.rerun()

# -------------------------------------------------------------
# 1. LANDING PAGE: AUTHENTICATION ROUTINES
# -------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("Yogakshemasabha Portal")

    # MODE A: EMAIL OTP LOGIN (DEFAULT SCREEN)
    if st.session_state.login_mode == "email":
        st.subheader("Login with your registered Household Email")
        
        if not st.session_state.otp_sent:
            input_email = st.text_input("Family Email Address").strip().lower()
            
            if st.button("Send Verification OTP"):
                if "@" not in input_email or "." not in input_email:
                    st.error("Please enter a valid email address.")
                else:
                    # Check if this email exists in the database
                    check_db = supabase.table("families").select("family_id").eq("email_id", input_email).execute()
                    
                    if check_db.data and len(check_db.data) > 0:
                        try:
                            # Send OTP via Supabase
                            # New code forcing a token/numeric OTP
                            supabase.auth.sign_in_with_otp({
                                "email": input_email,
                                "options": {
                                    "should_create_user": False  # Prevents random people from signing up if they aren't in your Excel table
                                            }
                                            })
                            st.session_state.auth_email = input_email
                            st.session_state.otp_sent = True
                            st.success(f"A 6-digit verification code has been sent to {input_email}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Auth Subsystem Error: {str(e)}")
                    else:
                        st.error("This email address is not found in our records. If you are logging in for the first time, please click the onboarding link below.")
            
            # THE LINK FOR USERS WITHOUT AN EMAIL
            st.write("---")
            if st.button("Forgot / No Email ID Registered? Click here to verify via Family Details"):
                st.session_state.login_mode = "backdoor"
                st.rerun()
                
        else:
            st.info(f"Logging in as: **{st.session_state.auth_email}**")
            otp_token = st.text_input("Enter 6-Digit Code received in your Email", max_chars=6).strip()
            
            col1, col2 = st.columns(2)
            with col1:
               if st.button("Verify & Login"):
                try:
                    # Officially verify the 6-digit token code with Supabase
                    auth_response = supabase.auth.verify_otp({
                        "email": st.session_state.auth_email,
                        "token": otp_token,
                        "type": "email"  # This tells it to check the email token queue
                    })
                    
                    # If verification succeeds, load their family profile
                    family_lookup = supabase.table("families").select("family_id").eq("email_id", st.session_state.auth_email).execute()
                    if family_lookup.data:
                        st.session_state.family_id = family_lookup.data[0]["family_id"]
                        st.session_state.logged_in = True
                        st.success("Login Successful!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Invalid OTP Code or Code Expired. Details: {str(e)}")
            with col2:
                if st.button("← Cancel / Change Email"):
                    st.session_state.otp_sent = False
                    st.session_state.auth_email = None
                    st.rerun()

    # MODE B: BACKDOOR ONBOARDING (NAME + ILLAM LOOKUP)
    elif st.session_state.login_mode == "backdoor":
        st.subheader("Verify via Household Details (Onboarding)")
        input_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)").strip()
        input_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)").strip()
        
        if st.button("Verify & Open Profile"):
            if input_head == "" or input_illam == "":
                st.error("Please fill in both fields.")
            else:
                # Look up row by family details
                response = supabase.table("families").select("family_id, head_of_family, email_id").ilike("head_of_family", f"%{input_head}%").ilike("illam_name", f"%{input_illam}%").execute()
                
                if response.data and len(response.data) > 0:
                    found_family = response.data[0]
                    registered_email = found_family.get("email_id")
                    
                    # CRITICAL RESTRICTION RULE: If they already registered an email, block the backdoor!
                    if registered_email and str(registered_email).strip().lower() != 'null' and str(registered_email).strip() != '':
                        st.error(f"🛑 Access Restricted! This profile already has a registered email address ({registered_email}). You must log in using the standard Household Email screen.")
                    else:
                        # Allow entry since email is blank
                        st.session_state.family_id = found_family["family_id"]
                        st.session_state.logged_in = True
                        st.success(f"Verified successfully! Welcome, {found_family['head_of_family']}.")
                        st.rerun()
                else:
                    st.error("Authentication Failed. No matching records found with those spelling variants.")
        
        if st.button("← Back to Primary Email Login"):
            st.session_state.login_mode = "email"
            st.rerun()


# -------------------------------------------------------------
# 2. APPLICATION DASHBOARD: CRUD OPERATIONS
# -------------------------------------------------------------
else:
    f_id = st.session_state.family_id
    
    # Sidebar
    st.sidebar.title("Navigation")
    if st.sidebar.button("Secure Log Out"):
        logout()

    st.title("Yogakshemasabha Portal Dashboard")
    
    # Fetch current data state
    family_data = supabase.table("families").select("*").eq("family_id", f_id).execute().data[0]

    # ---- EDIT HOUSEHOLD DATA FORM ----
    st.header("🏠 Household Information")
    with st.form("edit_family_form"):
        edit_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)", value=family_data.get('head_of_family', ''))
        edit_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)", value=family_data.get('illam_name', ''))
        edit_gothram = st.text_input("ഗോത്രം (Gothram)", value=family_data.get('gothram', ''))
        edit_address = st.text_area("മേൽവിലാസം (Address)", value=family_data.get('address', ''))
        
        if st.form_submit_button("Save Household Changes"):
            supabase.table("families").update({
                "head_of_family": edit_head.strip(),
                "illam_name": edit_illam.strip(),
                "gothram": edit_gothram.strip(),
                "address": edit_address.strip()
            }).eq("family_id", f_id).execute()
            st.success("Household information saved successfully!")
            st.rerun()

    # ---- DYNAMIC EMAIL REGISTRATION BAR ----
    # If a user logged in through the backdoor link, they can add their email address right here
    current_email = family_data.get('email_id')
    if not current_email or str(current_email).strip().lower() == 'null' or str(current_email).strip() == '':
        with st.status("📧 Phase 2 Security Setup Required", expanded=True):
            st.write("Please provide a primary email address for your household to lock this profile down to secure email OTP logins:")
            new_email = st.text_input("Enter Family Email Address", key="setup_email_input").strip().lower()
            
            if st.button("Save & Link Email"):
                if "@" not in new_email or "." not in new_email:
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        supabase.table("families").update({"email_id": new_email}).eq("family_id", f_id).execute()
                        st.success("Email address successfully linked! Moving forward, you must use the standard Email OTP screen.")
                        st.rerun()
                    except Exception as e:
                        if "unique constraint" in str(e).lower():
                            st.error("This email address is already claimed by another household registry profile.")
                        else:
                            st.error("Error saving address records.")
    else:
        st.info(f"🔒 Registered Login Identifier: **{current_email}**")

    # ---- READ/UPDATE/DELETE INDIVIDUAL FAMILY MEMBERS ----
    st.header("👥 Registered Family Members")
    members_data = supabase.table("members").select("*").eq("family_id", f_id).order("member_id").execute().data
    
    if members_data:
        for member in members_data:
            m_id = member['member_id']
            
            with st.expander(f"👤 {member['name']} ({member['relation'] or 'Member'})", expanded=False):
                with st.form(f"update_member_{m_id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        m_name = st.text_input("Name", value=member.get('name', ''))
                        m_relation = st.text_input("Relation", value=member.get('relation', ''))
                        m_dob = st.text_input("DOB (YYYY-MM-DD)", value=str(member.get('dob', '')) if member.get('dob') else '')
                        m_blood = st.text_input("Blood Group", value=member.get('blood_group', ''))
                    with col2:
                        m_phone = st.text_input("Phone Number", value=str(member.get('phone', '')) if member.get('phone') else '')
                        m_email = st.text_input("Email", value=member.get('email', ''))
                        m_qual = st.text_input("Qualification", value=member.get('qualification', ''))
                        m_job = st.text_input("Job / Occupation", value=member.get('job', ''))
                    
                    m_adhaar = st.text_input("Aadhaar Number", value=str(member.get('adhaar', '')) if member.get('adhaar') else '')
                    m_curr_addr = st.text_area("Current Address", value=member.get('current_address', ''))
                    
                    if st.form_submit_button(f"Save Profile Changes for {member['name']}"):
                        cleaned_dob = m_dob.strip() if m_dob.strip() != "" else None
                        
                        supabase.table("members").update({
                            "name": m_name.strip(),
                            "relation": m_relation.strip(),
                            "dob": cleaned_dob,
                            "blood_group": m_blood.strip(),
                            "phone": m_phone.strip(),
                            "email": m_email.strip(),
                            "qualification": m_qual.strip(),
                            "job": m_job.strip(),
                            "adhaar": m_adhaar.strip(),
                            "current_address": m_curr_addr.strip()
                        }).eq("member_id", m_id).execute()
                        st.success("Member record updated successfully.")
                        st.rerun()
                
                # DELETE BUTTON
                if st.button(f"❌ Delete {member['name']} from Database", key=f"del_btn_{m_id}"):
                    supabase.table("members").delete().eq("member_id", m_id).execute()
                    st.warning("Member has been removed.")
                    st.rerun()
    else:
        st.info("No members currently mapped to your household registry profile.")

    # ---- CREATE / ADD A NEW FAMILY MEMBER ----
    st.header("➕ Add New Family Member")
    with st.expander("Register a new member for this family"):
        with st.form("add_new_member_form", clear_on_submit=True):
            new_name = st.text_input("Full Name *")
            new_relation = st.text_input("Relation (e.g., Wife, Son, Daughter)")
            new_dob = st.text_input("DOB (YYYY-MM-DD)")
            new_blood = st.text_input("Blood Group")
            new_phone = st.text_input("Phone Number")
            new_email = st.text_input("Email Address")
            new_qual = st.text_input("Qualification")
            new_job = st.text_input("Job / Profession")
            new_adhaar = st.text_input("Aadhaar Number")
            new_curr_addr = st.text_area("Current Address", value="Same as above (മുകളിൽ നൽകിയ അതേ മേൽവിലാസം)")
            
            if st.form_submit_button("Add Member"):
                if new_name.strip() == "":
                    st.error("Name field is mandatory.")
                else:
                    cleaned_dob = new_dob.strip() if new_dob.strip() != "" else None
                    
                    supabase.table("members").insert({
                        "family_id": f_id,
                        "name": new_name.strip(),
                        "relation": new_relation.strip(),
                        "dob": cleaned_dob,
                        "blood_group": new_blood.strip(),
                        "phone": new_phone.strip(),
                        "email": new_email.strip(),
                        "qualification": new_qual.strip(),
                        "job": new_job.strip(),
                        "adhaar": new_adhaar.strip(),
                        "current_address": new_curr_addr.strip()
                    }).execute()
                    
                    st.success(f"{new_name.strip()} has been successfully registered under your family profile!")
                    st.rerun()
