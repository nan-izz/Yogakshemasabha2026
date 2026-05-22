import os
import datetime
from supabase import create_client, Client

# Initialize Supabase Client Connection
url = os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url")
key = os.environ.get("SUPABASE_KEY") or os.environ.get("supabase_key")

if not url:
    import streamlit as st
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)


def fetch_admin_config():
    try:
        return supabase.table("admin_config").select("*").eq("id", 1).execute().data[0]
    except Exception:
        try:
            return supabase.table("admin_config").select("*").eq("id", 1).execute().data[0]
        except:
            return {"username": "sabhaadmin", "password": "admin123"}


def check_family_email_exists(email):
    res = supabase.table("families").select("family_id").eq("email_id", email).execute()
    return res.data and len(res.data) > 0


def fetch_family_by_email(email):
    res = supabase.table("families").select("family_id").eq("email_id", email).execute()
    return res.data[0] if res.data else None


def verify_backdoor_details(head_name, illam_name):
    return supabase.table("families").select("family_id, head_of_family, email_id").ilike("head_of_family",
                                                                                          f"%{head_name}%").ilike(
        "illam_name", f"%{illam_name}%").execute().data


def fetch_single_family(family_id):
    return supabase.table("families").select("*").eq("family_id", family_id).execute().data[0]


def update_family_header(family_id, head, illam, gothram, address):
    supabase.table("families").update({
        "head_of_family": head.strip(),
        "illam_name": illam.strip(),
        "gothram": gothram.strip(),
        "address": address.strip()
    }).eq("family_id", family_id).execute()


def link_family_email(family_id, email):
    supabase.table("families").update({"email_id": email}).eq("family_id", family_id).execute()


def fetch_family_members(family_id):
    return supabase.table("members").select("*").eq("family_id", family_id).order("member_id").execute().data


def fetch_recent_families_global(limit=10):
    try:
        # Pulls only the top 10 rows from Supabase, ordered by their ID or creation
        # (If you have an updated_at column, replace family_id with updated_at)
        return supabase.table("families").select("*").order("family_id", desc=True).limit(limit).execute().data
    except Exception:
        return supabase.table("families").select("*").order("family_id", desc=True).limit(limit).execute().data

def search_families_global(search_term):
    try:
        # Dynamically filter rows on Supabase's server side instead of downloading everything to Python
        return supabase.table("families").select("*")\
            .or_(f"head_of_family.ilike.%{search_term}%,illam_name.ilike.%{search_term}%,address.ilike.%{search_term}%")\
            .order("head_of_family").execute().data
    except Exception:
        return supabase.table("families").select("*")\
            .or_(f"head_of_family.ilike.%{search_term}%,illam_name.ilike.%{search_term}%,address.ilike.%{search_term}%")\
            .order("head_of_family").execute().data

def fetch_all_members_global():
    try:
        return supabase.table("members").select("name, relation, dob, phone, family_id").execute().data
    except Exception:
        return supabase.table("members").select("name, relation, dob, phone, family_id").execute().data


def submit_pending_approval(table, action, email, payload, target_id=None):
    supabase.table("pending_approvals").insert({
        "target_table": table,
        "action_type": action,
        "requested_by": email,
        "target_id": target_id,
        "change_payload": payload
    }).execute()


def fetch_pending_approvals():
    return supabase.table("pending_approvals").select("*").order("created_at").execute().data


def process_approval_action(req_id, action, table, payload, target_id):
    if action == "INSERT":
        supabase.table(table).insert(payload).execute()
    elif action == "UPDATE":
        id_col = "family_id" if table == "families" else "member_id"
        supabase.table(table).update(payload).eq(id_col, target_id).execute()
    elif action == "DELETE":
        id_col = "family_id" if table == "families" else "member_id"
        supabase.table(table).delete().eq(id_col, target_id).execute()

    supabase.table("pending_approvals").delete().eq("approval_id", req_id).execute()


def reject_pending_approval(req_id):
    supabase.table("pending_approvals").delete().eq("approval_id", req_id).execute()


def admin_direct_save_member(m_id, payload):
    supabase.table("members").update(payload).eq("member_id", m_id).execute()


def admin_direct_delete_member(m_id):
    supabase.table("members").delete().eq("member_id", m_id).execute()


def admin_direct_save_family(f_id, payload):
    supabase.table("families").update(payload).eq("family_id", f_id).execute()


def admin_direct_delete_family(f_id):
    supabase.table("families").delete().eq("family_id", f_id).execute()


def admin_update_credentials(username, password):
    supabase.table("admin_config").update({"username": username, "password": password}).eq("id", 1).execute()


def send_supabase_otp(email):
    # Changing should_create_user to True allows Supabase to dynamically
    # provision an auth record for the email when they verify their first code!
    supabase.auth.sign_in_with_otp({"email": email, "options": {"should_create_user": True}})

def fetch_all_families_global():
    try:
        # Resolves the AttributeError by restoring the global hook with retry safety
        return supabase.table("families").select("*").order("head_of_family").execute().data
    except Exception:
        return supabase.table("families").select("*").order("head_of_family").execute().data

def fetch_district_sabha_report_data():
    try:
        # Pulls targeted reporting fields along with the family relation pointer
        return supabase.table("members").select("name, dob, blood_group, current_address, phone, created_at, family_id").execute().data
    except Exception:
        return supabase.table("members").select("name, dob, blood_group, current_address, phone, created_at, family_id").execute().data