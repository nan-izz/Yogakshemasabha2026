import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os

import io

# --- SETUP SUPABASE ---
# These secrets will be stored securely on the hosting server
url = "https://oommuvndvdvcawjggcia.supabase.co"
key = "sb_publishable_j1qlCsBzk3nt0_7if-eZ1g_4OH_4hWn"

supabase: Client = create_client(url, key)

# --- SESSION STATE MANAGEMENT ---
if "role" not in st.session_state:
    st.session_state.role = None
if "user_phone" not in st.session_state:
    st.session_state.user_phone = None
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False

st.title("Community Data Portal")

# --- LOGIN SCREEN ---
if st.session_state.role is None:
    tab1, tab2 = st.tabs(["User Login (OTP)", "Admin Login"])

    # USER LOGIN
    with tab1:
        st.subheader("Login with your Mobile Number")
        phone = st.text_input("Mobile Number (Include country code, e.g., +91)")

        if not st.session_state.otp_sent:
            if st.button("Send OTP"):
                if phone:
                    try:
                        supabase.auth.sign_in_with_otp({"phone": phone})
                        st.session_state.otp_sent = True
                        st.session_state.temp_phone = phone
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error sending OTP. Ensure number is registered. {e}")
                else:
                    st.warning("Please enter a phone number.")
        else:
            otp = st.text_input("Enter 6-digit OTP")
            if st.button("Verify & Login"):
                try:
                    res = supabase.auth.verify_otp({"phone": st.session_state.temp_phone, "token": otp, "type": "sms"})
                    if res.user:
                        st.session_state.role = "user"
                        st.session_state.user_phone = st.session_state.temp_phone
                        st.rerun()
                except Exception as e:
                    st.error("Invalid OTP. Try again.")

    # ADMIN LOGIN
    with tab2:
        st.subheader("Implementer Login")
        admin_user = st.text_input("Username")
        admin_pass = st.text_input("Password", type="password")
        if st.button("Admin Login"):
            if admin_user == "admin" and admin_pass == "admin":
                st.session_state.role = "admin"
                st.rerun()
            else:
                st.error("Invalid Admin Credentials")

# --- ADMIN DASHBOARD ---
elif st.session_state.role == "admin":
    st.success("Logged in as Admin")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.subheader("Upload Excel Database")
    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "csv"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.write("Preview of Uploaded Data:")
            st.dataframe(df.head(3))

            if st.button("Sync Data to Cloud Database"):
                with st.spinner("Uploading..."):
                    mapped_data = []
                    for index, row in df.iterrows():
                        phone_val = str(row.get('ഫോൺ നമ്പർ (Phone)', '')).replace('.0', '').strip()
                        if phone_val and phone_val != 'nan':
                            if not phone_val.startswith('+'):
                                phone_val = '+91' + phone_val

                            mapped_data.append({
                                "phone": phone_val,
                                "name": str(row.get('ഗൃഹനാഥന്റെ പേര് (Name of Gruhanathan)', '')),
                                "address": str(row.get('മേൽവിലാസം (Address)', '')),
                                "job": str(row.get('തൊഴിൽ (Job)', ''))
                            })

                    for record in mapped_data:
                        existing = supabase.table('user_data').select("*").eq('phone', record['phone']).execute()
                        if len(existing.data) > 0:
                            supabase.table('user_data').update(record).eq('phone', record['phone']).execute()
                        else:
                            supabase.table('user_data').insert(record).execute()

                st.success("Database successfully synchronized!")
        except Exception as e:
            st.error(f"Error reading file: {e}")

# --- END USER DASHBOARD ---
elif st.session_state.role == "user":
    st.success(f"Welcome!")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

    response = supabase.table('user_data').select("*").eq('phone', st.session_state.user_phone).execute()

    if len(response.data) > 0:
        user_record = response.data[0]

        st.subheader("Your Profile")
        with st.form("user_update_form"):
            new_name = st.text_input("Name", value=user_record.get('name', ''))
            new_address = st.text_area("Address", value=user_record.get('address', ''))
            new_job = st.text_input("Job", value=user_record.get('job', ''))

            if st.form_submit_button("Update Details"):
                updated_data = {
                    "name": new_name,
                    "address": new_address,
                    "job": new_job
                }
                supabase.table('user_data').update(updated_data).eq('phone', st.session_state.user_phone).execute()
                st.success("Details updated successfully!")
    else:
        st.warning("No data found for this number. Please contact the administrator.")
