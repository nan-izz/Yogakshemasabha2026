import streamlit as st
import os
from supabase import create_client, Client

# Initialize Supabase Client
url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Initialize Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "family_id" not in st.session_state:
    st.session_state.family_id = None
if "login_mode" not in st.session_state:
    st.session_state.login_mode = "email"  # Toggle between 'email' and 'backdoor'

# ---- LOGOUT FUNCTIONALITY ----
def logout():
    st.session_state.logged_in = False
    st.session_state.family_id = None
    st.session_state.login_mode = "email"
    st.rerun()


# ---- 1. LANDING PAGE / LOGIN MODES ----
if not st.session_state.logged_in:
    st.title("Yogakshemasabha Portal")

    # MODE A: PRIMARY EMAIL LOGIN
    if st.session_state.login_mode == "email":
        st.subheader("Login with your registered Household Email")
        input_email = st.text_input("Family Email Address").strip().lower()
        
        if st.button("Log In with Email"):
            if input_email == "":
                st.error("Please enter your email address.")
            else:
                # Search database for this exact email
                response = supabase.table("families").select("family_id, head_of_family").eq("email_id", input_email).execute()
                
                if response.data and len(response.data) > 0:
                    st.session_state.logged_in = True
                    st.session_state.family_id = response.data[0]["id"]
                    st.success(f"Welcome back, {response.data[0]['head_of_family']}!")
                    st.rerun()
                else:
                    st.error("This email is not registered yet. If this is your first time onboarding, please click the link below.")
        
        # Link to switch to Name + Illam login
        if st.button("Forgot / No Email ID Registered? Click here to verify via Family Details"):
            st.session_state.login_mode = "backdoor"
            st.rerun()

    # MODE B: BACKDOOR ONBOARDING (NAME + ILLAM)
    elif st.session_state.login_mode == "backdoor":
        st.subheader("Verify via Household Details (Onboarding)")
        input_head = st.text_input("ഗൃഹനാഥന്റെ പേര് (Head of Family Name)").strip()
        input_illam = st.text_input("ഇല്ലപ്പേര് (Illam Name)").strip()
        
        if st.button("Verify & Open Profile"):
            if input_head == "" or input_illam == "":
                st.error("Please fill in both fields.")
            else:
                # Look up the profile matching the credentials
                response = supabase.table("families").select("id, head_of_family, email_id").ilike("head_of_family", f"%{input_head}%").ilike("illam_name", f"%{input_illam}%").execute()
                
                if response.data and len(response.data) > 0:
                    found_family = response.data[0]
                    registered_email = found_family.get("email_id")
                    
                    # CRITICAL RESTRICTION: If they have an email, block them from using this backdoor!
                    if registered_email and str(registered_email).strip().lower() != 'null' and str(registered_email).strip() != '':
                        st.error(f"🛑 Access Restricted! This profile already has a registered email address ({registered_email}). You must log in using the Primary Email screen.")
                    else:
                        # Allow entry since email_id is missing/blank
                        st.session_state.logged_in = True
                        st.session_state.family_id = found_family["id"]
                        st.success(f"Verified successfully! Welcome, {found_family['head_of_family']}.")
                        st.rerun()
                else:
                    st.error("Authentication Failed. No matching records found.")
        
        # Link to go back to email screen
        if st.button("← Back to Email Login"):
            st.session_state.login_mode = "email"
            st.rerun()


# ---- 2. LOGGED IN MEMBER PORTAL ----
else:
    f_id = st.session_state.family_id
    
    # Sidebar layout for Profile & Logout
    if st.sidebar.button("Log Out"):
        logout()

    st.title("Yogakshemasabha Member Portal")
    
    # Fetch the family data
    family_data = supabase.table("families").select("*").eq("id", f_id).execute().data[0]
    
    st.subheader("Your Household Information")
    st.write(f"**Head of Family:** {family_data['head_of_family']}")
    st.write(f"**Illam Name:** {family_data['illam_name']}")
    st.write(f"**Address:** {family_data['address']}")
    
    # ---- DYNAMIC EMAIL REGISTRATION/DISPLAY ----
    current_email = family_data.get('email_id')
    
    if not current_email or str(current_email).strip().lower() == 'null' or str(current_email).strip() == '':
        with st.status("📧 Phase 2 Security Setup Required", expanded=True):
            st.write("We are setting up secure email authentication. Please link a primary email address for your household:")
            new_email = st.text_input("Enter Family Email Address", key="setup_email_input").strip().lower()
            
            if st.button("Save & Link Email"):
                if "@" not in new_email or "." not in new_email:
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        # Update the email_id column in Supabase
                        supabase.table("families").update({"email_id": new_email}).eq("id", f_id).execute()
                        st.success("Email address successfully linked! From now on, you must use this email to log in.")
                        st.rerun()
                    except Exception as e:
                        # This triggers if someone tries to use an email that another family already claimed
                        if "unique constraint" in str(e).lower():
                            st.error("This email address is already registered to another family profile. Please use a unique email.")
                        else:
                            st.error("An error occurred while saving your email. Please try again.")
    else:
        st.info(f"🔒 Registered Login Identifier: **{current_email}**")

    # ---- DISPLAY FAMILY MEMBERS ----
    st.subheader("Registered Family Members")
    members_data = supabase.table("members").select("*").eq("family_id", f_id).execute().data
    
    if members_data:
        for member in members_data:
            with st.container(border=True):
                st.write(f"**Name:** {member['name']} ({member['relation']})")
                if member['phone']: st.write(f"Phone: {member['phone']}")
                if member['blood_group']: st.write(f"Blood Group: {member['blood_group']}")
                if member['qualification']: st.write(f"Qualification: {member['qualification']}")
                if member['job']: st.write(f"Job: {member['job']}")
