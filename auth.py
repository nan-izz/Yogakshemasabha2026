import datetime

BLOOD_GROUPS = ['Not Identified', 'A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']


def validate_aadhaar(aadhaar_str):
    cleaned = str(aadhaar_str).replace(" ", "").strip()
    if cleaned == "" or cleaned.lower() in ["none", "null"]:
        return True, ""
    if len(cleaned) == 12 and cleaned.isdigit():
        return True, cleaned
    return False, None


def calculate_voter_roll(all_members, all_families, target_date):
    fam_map = {x["family_id"]: x for x in all_families}
    voters = []

    for m in all_members:
        if m.get("dob"):
            try:
                dob_parsed = datetime.datetime.strptime(str(m["dob"]), "%Y-%m-%d").date()
                age = (target_date - dob_parsed).days / 365.25
                if age >= 18.0:
                    f_info = fam_map.get(m["family_id"], {})
                    voters.append({
                        "Name": m["name"],
                        "Relation": m["relation"],
                        "Date of Birth": m["dob"],
                        "Calculated Age": round(age, 1),
                        "Phone Contact": m["phone"],
                        "Head of Family": f_info.get("head_of_family", "N/A"),
                        "Illam Name": f_info.get("illam_name", "N/A")
                    })
            except:
                pass
    return voters