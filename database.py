import os
import streamlit as st
from supabase import create_client, Client

# Initialize Supabase Client Connection
url = os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url")
key = os.environ.get("SUPABASE_KEY") or os.environ.get("supabase_key")

if not url:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)


# -------------------------------------------------------------
# HIGH-SPEED MEMORY CACHE WRAPPERS (READ OPERATORS)
# -------------------------------------------------------------

@st.cache_data(ttl=600)
def fetch_all_members_global():
    try:
        return supabase.table("members").select("name, relation, dob, phone, family_id, blood_group").execute().data
    except Exception:
        return supabase.table("members").select("name, relation, dob, phone, family_id, blood_group").execute().data


@st.cache_data(ttl=600)
def fetch_all_families_global():
    try:
        return supabase.table("families").select("*").order("head_of_family").execute().data
    except Exception:
        return supabase.table("families").select("*").order("head_of_family").execute().data


@st.cache_data(ttl=3600)
def fetch_admin_config():
    try:
        return supabase.table("admin_config").select("*").eq("id", 1).execute().data[0]
    except Exception:
        return {"username": "sabhaadmin", "password": "admin123", "yearly_verification_active": False,
                "base_family_fee": 700, "base_member_threshold": 4, "additional_member_fee": 100}


@st.cache_data(ttl=300)
def fetch_recent_families_global(limit=10):
    try:
        return supabase.table("families").select("*").order("updated_at", desc=True).limit(limit).execute().data
    except Exception:
        return supabase.table("families").select("*").order("family_id", desc=True).limit(limit).execute().data


@st.cache_data(ttl=60)
def search_families_global(search_term):
    try:
        return supabase.table("families").select("*").or_(
            f"head_of_family.ilike.%{search_term}%,illam_name.ilike.%{search_term}%,address.ilike.%{search_term}%").order(
            "head_of_family").execute().data
    except Exception:
        return supabase.table("families").select("*").or_(
            f"head_of_family.ilike.%{search_term}%,illam_name.ilike.%{search_term}%,address.ilike.%{search_term}%").order(
            "head_of_family").execute().data


def fetch_single_family(family_id):
    res = supabase.table("families").select("*").eq("family_id", family_id).execute()
    return res.data[0] if res.data else {}


def fetch_family_members(family_id):
    return supabase.table("members").select("*").eq("family_id", family_id).order("member_id").execute().data


def fetch_pending_approvals():
    return supabase.table("pending_approvals").select("*").order("approval_id").execute().data


def check_family_email_exists(email):
    res = supabase.table("families").select("family_id").eq("email_id", email.strip().lower()).execute()
    return len(res.data) > 0


def fetch_family_by_email(email):
    res = supabase.table("families").select("*").eq("email_id", email.strip().lower()).execute()
    return res.data[0] if res.data else None


def verify_backdoor_details(head, illam):
    return supabase.table("families").select("*").eq("head_of_family", head.strip()).eq("illam_name",
                                                                                        illam.strip()).execute().data


def check_if_user_has_pending_requests(email):
    res = supabase.table("pending_approvals").select("approval_id").eq("requested_by", email.strip().lower()).execute()
    return len(res.data) > 0


# -------------------------------------------------------------
# MASTER TRANSACTION WRITE ENGINE (AUTOMATIC CACHE FLUSHING)
# -------------------------------------------------------------

def process_approval_action(approval_id, action, table, payload, target_id=None):
    try:
        family_email = None
        req_lookup = supabase.table("pending_approvals").select("requested_by").eq("approval_id", approval_id).execute()
        if req_lookup.data: family_email = req_lookup.data[0].get("requested_by")

        if table == "families" and action == "INSERT":
            fam_res = supabase.table("families").insert(
                {"head_of_family": payload.get("head_of_family"), "illam_name": payload.get("illam_name"),
                 "gothram": payload.get("gothram"), "address": payload.get("address"),
                 "email_id": payload.get("email_id")}).execute()
            if fam_res.data:
                supabase.table("members").insert(
                    {"family_id": fam_res.data[0]["family_id"], "name": payload.get("head_of_family"),
                     "relation": "Head of Family", "dob": payload.get("head_dob"), "phone": payload.get("head_phone"),
                     "current_address": payload.get("address")}).execute()
        elif table == "members" and action == "INSERT":
            supabase.table("members").insert(payload).execute()
        elif action == "UPDATE":
            if table == "families":
                supabase.table("families").update(payload).eq("family_id", target_id).execute()
            elif table == "members":
                supabase.table("members").update(payload).eq("member_id", target_id).execute()
        elif action == "DELETE":
            if table == "members":
                supabase.table("members").delete().eq("member_id", target_id).execute()
            elif table == "families":
                supabase.table("members").delete().eq("family_id", target_id).execute()
                supabase.table("families").delete().eq("family_id", target_id).execute()

        if family_email:
            supabase.table("families").update({
                                                  "admin_notification": f"✅ Your recent request to {action.lower()} records inside '{table}' was APPROVED by the committee."}).eq(
                "email_id", family_email).execute()

        supabase.table("pending_approvals").delete().eq("approval_id", approval_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Write Execution Failure: {str(e)}")
        raise e


def submit_pending_approval(table, action, requested_by, payload, target_id=None):
    return supabase.table("pending_approvals").insert(
        {"target_table": table, "action_type": action, "requested_by": requested_by, "change_payload": payload,
         "target_id": target_id}).execute()


def submit_new_family_registration(email, payload):
    return supabase.table("pending_approvals").insert(
        {"target_table": "families", "action_type": "INSERT", "requested_by": email,
         "change_payload": payload}).execute()


def reject_pending_approval(approval_id):
    req_lookup = supabase.table("pending_approvals").select("requested_by, action_type, target_table").eq("approval_id",
                                                                                                          approval_id).execute()
    if req_lookup.data:
        family_email = req_lookup.data[0].get("requested_by")
        action = req_lookup.data[0].get("action_type")
        table = req_lookup.data[0].get("target_table")
        if family_email:
            supabase.table("families").update({
                                                  "admin_notification": f"❌ Your recent request to {action.lower()} records inside '{table}' was REJECTED by the managing committee."}).eq(
                "email_id", family_email).execute()

    res = supabase.table("pending_approvals").delete().eq("approval_id", approval_id).execute()
    st.cache_data.clear()
    return res


def clear_user_notification(family_id):
    res = supabase.table("families").update({"admin_notification": None}).eq("family_id", family_id).execute()
    st.cache_data.clear()
    return res


def update_family_header(family_id, head, illam, gothram, address):
    res = supabase.table("families").update(
        {"head_of_family": head, "illam_name": illam, "gothram": gothram, "address": address,
         "updated_at": "now()"}).eq("family_id", family_id).execute()
    st.cache_data.clear()
    return res


def admin_direct_save_member(member_id, payload):
    res = supabase.table("members").update(payload).eq("member_id", member_id).execute()
    st.cache_data.clear()
    return res


def admin_direct_delete_member(member_id):
    res = supabase.table("members").delete().eq("member_id", member_id).execute()
    st.cache_data.clear()
    return res


def admin_direct_delete_family(family_id):
    supabase.table("members").delete().eq("family_id", family_id).execute()
    res = supabase.table("families").delete().eq("family_id", family_id).execute()
    st.cache_data.clear()
    return res


def link_family_email(family_id, email):
    res = supabase.table("families").update({"email_id": email}).eq("family_id", family_id).execute()
    st.cache_data.clear()
    return res


def update_global_verification_toggle(is_active, base_fee, threshold, additional_fee):
    res = supabase.table("admin_config").update({
        "yearly_verification_active": is_active, "base_family_fee": base_fee,
        "base_member_threshold": threshold, "additional_member_fee": additional_fee
    }).eq("id", 1).execute()
    st.cache_data.clear()
    return res


def update_family_verification_state(family_id, status, payment_ref=None, receipt_url=None):
    update_data = {"verification_status": status, "updated_at": "now()"}
    if payment_ref: update_data["payment_reference"] = payment_ref
    if receipt_url: update_data["payment_receipt_url"] = receipt_url
    res = supabase.table("families").update(update_data).eq("family_id", family_id).execute()
    st.cache_data.clear()
    return res


def update_admin_upi_credentials(upi_id, qr_file_binary=None):
    update_data = {"upi_id": upi_id}
    if qr_file_binary is not None:
        bucket_name = "upi_assets"
        file_path = "qr_code_live.png"
        supabase.storage.from_(bucket_name).upload(path=file_path, file=qr_file_binary,
                                                   file_options={"cache-control": "3600", "upsert": "true"})
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        update_data["upi_qr_url"] = public_url
    res = supabase.table("admin_config").update(update_data).eq("id", 1).execute()
    st.cache_data.clear()
    return res


def admin_update_credentials(username, password):
    res = supabase.table("admin_config").update({"username": username, "password": password}).eq("id", 1).execute()
    st.cache_data.clear()
    return res


def send_supabase_otp(email):
    return supabase.auth.sign_in_with_otp({"email": email.strip().lower()})

def verify_supabase_otp(email, token):
    """
    Submits the 6-digit token to Supabase Auth to verify its validity.
    Returns True if valid, False if incorrect or expired.
    """
    try:
        # Use Supabase's native type verification handler
        res = supabase.auth.verify_otp({
            "email": email.strip().lower(),
            "token": token.strip(),
            "type": "magiclink"  # or "signup" depending on your auth scheme configuration
        })
        # If a valid session user profile is returned, the OTP is correct
        if res.user:
            return True
        return False
    except Exception as e:
        print(f"OTP Cryptographic Verification Engine Failure: {str(e)}")
        return False