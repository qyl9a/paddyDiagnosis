import json
import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATA_FILE = "data.json"

UPLOAD_ROOT = os.path.join("static", "images", "symptoms")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def category_to_folder(category_slug: str) -> str:
    # your UI uses "whole" but folder name should be "whole"
    return "whole" if category_slug == "whole" else category_slug
def save_uploaded_symptom_image(file_storage, category_slug, sym_id):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()

   

    folder = os.path.join(UPLOAD_ROOT, category_slug)
    os.makedirs(folder, exist_ok=True)

    saved_name = f"{sym_id}{ext}"
    save_path = os.path.join(folder, saved_name)
    file_storage.save(save_path)

    # path stored in JSON must be relative to /static
    return f"images/symptoms/{category_slug}/{saved_name}"



CATEGORY_KEYS = {
    "leaf": "leaf",
    "stem": "stem",
    "panicle": "panicle",
    "whole": "Whole Plant / General"
}

TEMPLATE_MAP = {
    "leaf": "leaf.html",
    "stem": "stem.html",
    "panicle": "panicle.html",
    "whole": "whole.html"
}

NEXT_STEP = {"leaf": "stem", "stem": "panicle", "panicle": "whole", "whole": "diagnose"}
PREV_STEP = {"leaf": None, "stem": "leaf", "panicle": "stem", "whole": "panicle"}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "leaf": [],
            "stem": [],
            "panicle": [],
            "Whole Plant / General": [],
            "disease": []
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_all_symptoms(data):
    """put all symptom categories into one list for admin dropdown & mapping."""
    all_symptoms = []
    for key in ["leaf", "stem", "panicle", "Whole Plant / General"]:
        all_symptoms.extend(data.get(key, []))
    return all_symptoms


def get_selected_set():
    return set(session.get("selected_symptoms", []))


def save_selected_set(selected_set):
    session["selected_symptoms"] = sorted(selected_set)


def get_category_ids(data, category_slug):
    json_key = CATEGORY_KEYS[category_slug]
    items = data.get(json_key, [])
    return {s["id"] for s in items if isinstance(s, dict) and "id" in s}


def render_category(category_slug):
    data = load_data()
    json_key = CATEGORY_KEYS[category_slug]
    symptoms_list = data.get(json_key, [])
    selected = get_selected_set()

    return render_template(
        TEMPLATE_MAP[category_slug],
        symptoms_list=symptoms_list,
        selected_symptoms=selected,
        next_step=NEXT_STEP.get(category_slug),
        prev_step=PREV_STEP.get(category_slug),
    )


def find_symptom_location(data, sym_id):
    """
    Returns (json_key, index, symptom_obj) if found, else (None, None, None).
    """
    for json_key in ["leaf", "stem", "panicle", "Whole Plant / General"]:
        items = data.get(json_key, [])
        for i, s in enumerate(items):
            if isinstance(s, dict) and s.get("id") == sym_id:
                return json_key, i, s
    return None, None, None


def symptom_used_by_diseases(data, sym_id):
    """Return list of disease names that reference this symptom id."""
    used_by = []
    for d in data.get("disease", []):
        if sym_id in d.get("symptoms", []):
            used_by.append(d.get("name", d.get("id", "Unknown disease")))
    return used_by


# ---------------- PUBLIC ROUTES ----------------
@app.route("/")
def homepage():
    return render_template("home.html")


@app.route("/leaf")
def leaf():
    return render_category("leaf")


@app.route("/stem")
def stem():
    return render_category("stem")


@app.route("/panicle")
def panicle():
    return render_category("panicle")


@app.route("/whole")
def whole():
    return render_category("whole")


@app.route("/update_selection/<category_slug>", methods=["POST"])
def update_selection(category_slug):
    if category_slug not in CATEGORY_KEYS:
        return redirect(url_for("homepage"))

    data = load_data()
    category_ids = get_category_ids(data, category_slug)

    page_selected = set(request.form.getlist("symptoms"))
    selected = get_selected_set()

    selected -= category_ids
    selected |= (page_selected & category_ids)

    save_selected_set(selected)

    next_slug = NEXT_STEP.get(category_slug)
    return redirect(url_for(next_slug)) if next_slug else redirect(url_for("whole"))


@app.route("/diagnose", methods=["GET"])
def diagnose():
    data = load_data()
    diseases = data.get("disease", [])
    selected_symptoms = list(get_selected_set())
    selected_set = set(selected_symptoms)

    scores = []
    for dis in diseases:
        dis_symptoms = dis.get("symptoms", [])
        if not dis_symptoms:
            continue

        logic = dis.get("logic", "OR").upper()
        matches = [s for s in dis_symptoms if s in selected_set]

        if logic == "AND":
            rule_pass = set(dis_symptoms).issubset(selected_set)
        
        else:
            rule_pass = len(matches) > 0
        
        if not rule_pass:
            continue
    

        confidence = round((len(matches) / len(dis_symptoms)) * 100, 2)

        
        dis_copy = dis.copy()
        dis_copy["match_count"] = len(matches)
        dis_copy["matches"] = matches
        dis_copy["confidence"] = confidence
        dis_copy["logic"] = logic
        scores.append(dis_copy)

    # Sort by number of matches (highest first)
    scores.sort(key=lambda x: x["match_count"], reverse=True)

    session.pop("selected_symptoms", None)

    return render_template(
        "result.html",
        diagnosis=scores,
        selected_symptoms=selected_symptoms
    )


@app.route("/clear")
def clear():
    session.pop("selected_symptoms", None)
    flash("Selections cleared.")
    return redirect(url_for("homepage"))


# ---------------- ADMIN ROUTES ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "admin" and password == "paddy123":
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid Credentials. Please try again.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("homepage"))


@app.route("/admin")
def admin_dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()

    # Make template-friendly aliases
    data["symptoms"] = build_all_symptoms(data)
    data["diseases"] = data.get("disease", [])

    # Also pass categorized symptoms for symptom management table
    categorized_symptoms = {
        "leaf": data.get("leaf", []),
        "stem": data.get("stem", []),
        "panicle": data.get("panicle", []),
        "whole": data.get("Whole Plant / General", []),
    }

    return render_template(
        "admin.html",
        data=data,
        categorized_symptoms=categorized_symptoms,
        category_keys=CATEGORY_KEYS
    )


@app.route("/admin/add", methods=["POST"])
def add_disease():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()
    name = request.form["name"].strip()
    new_id = name.lower().replace(" ", "_")

    logic = request.form.get("logic", "OR").strip().upper()
    if logic not in ["AND", "OR"]:
        logic = "OR"

    mgmt_raw = request.form.get("management", "").strip()
    if "\n" in mgmt_raw:
        management_list = [line.strip() for line in mgmt_raw.splitlines() if line.strip()]
    else:
        management_list = [m.strip() for m in mgmt_raw.split(",") if m.strip()]

    new_disease = {
        "id": new_id,
        "name": name,
        "type": request.form.get("type", "").strip(),
        "severity": request.form.get("severity", "").strip(),
        "logic": logic,
        "description": request.form.get("description", "").strip(),
        "management": management_list,
        "symptoms": request.form.getlist("symptoms"),
    }

    data.setdefault("disease", []).append(new_disease)
    save_data(data)

    flash(f"Rule for '{name}' added successfully!")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<disease_id>")
def delete_disease(disease_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()
    diseases = data.get("disease", [])
    original_count = len(diseases)

    data["disease"] = [d for d in diseases if d.get("id") != disease_id]

    if len(data["disease"]) < original_count:
        save_data(data)
        flash("Rule deleted successfully.")
    else:
        flash("Error: Rule not found.")

    return redirect(url_for("admin_dashboard"))


# ----------- NEW: SYMPTOM ADMIN (ADD/DELETE) -----------
@app.route("/admin/symptom/add", methods=["POST"])
def add_symptom():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()

    category_slug = request.form.get("category", "").strip()
    sym_id = request.form.get("id", "").strip()
    label = request.form.get("label", "").strip()

    if category_slug not in CATEGORY_KEYS:
        flash("Invalid category.")
        return redirect(url_for("admin_dashboard"))

    if not sym_id or not label:
        flash("Symptom ID and label are required.")
        return redirect(url_for("admin_dashboard"))

    # prevent duplicates across ALL categories
    all_ids = {s.get("id") for s in build_all_symptoms(data) if isinstance(s, dict)}
    if sym_id in all_ids:
        flash(f"Symptom ID '{sym_id}' already exists. Use a unique ID.")
        return redirect(url_for("admin_dashboard"))

    # ---- optional image upload ----
    image_file = request.files.get("image")
    image_path = ""  # relative path stored in JSON, e.g. images/symptoms/leaf/leaf_xxx.webp

    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            flash("Invalid image type. Allowed: png, jpg, jpeg, webp.")
            return redirect(url_for("admin_dashboard"))

        folder = category_to_folder(category_slug)
        save_dir = os.path.join(UPLOAD_ROOT, folder)
        os.makedirs(save_dir, exist_ok=True)

        ext = image_file.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"{sym_id}.{ext}")

        full_path = os.path.join(save_dir, filename)
        image_file.save(full_path)

        image_path = f"images/symptoms/{folder}/{filename}"

    json_key = CATEGORY_KEYS[category_slug]

    symptom_obj = {"id": sym_id, "label": label}
    if image_path:
        symptom_obj["img"] = image_path

    data.setdefault(json_key, []).append(symptom_obj)
    save_data(data)

    flash(f"Symptom '{label}' added to {category_slug}.")
    return redirect(url_for("admin_dashboard"))



@app.route("/admin/symptom/delete/<sym_id>")
def delete_symptom(sym_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()

    # Block delete if used by any disease
    used_by = symptom_used_by_diseases(data, sym_id)
    if used_by:
        flash(f"Cannot delete '{sym_id}'. It is used by: {', '.join(used_by)}")
        return redirect(url_for("admin_dashboard"))

    json_key, idx, sym_obj = find_symptom_location(data, sym_id)
    if json_key is None:
        flash("Symptom not found.")
        return redirect(url_for("admin_dashboard"))

    data[json_key].pop(idx)
    save_data(data)
    flash(f"Symptom '{sym_id}' deleted successfully.")
    return redirect(url_for("admin_dashboard"))
@app.route("/admin/symptom/update", methods=["POST"])
def update_symptom():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    data = load_data()

    old_id = request.form.get("original_id", "").strip()
    old_cat = request.form.get("original_category", "").strip()
    new_cat = request.form.get("category", "").strip()
    new_label = request.form.get("label", "").strip()

    if not old_id:
        flash("Missing symptom id.")
        return redirect(url_for("admin_dashboard"))

    if new_cat not in CATEGORY_KEYS:
        flash("Invalid category.")
        return redirect(url_for("admin_dashboard"))

    if not new_label:
        flash("Label is required.")
        return redirect(url_for("admin_dashboard"))

    # find symptom in old location
    json_key_old, idx_old, sym_obj = find_symptom_location(data, old_id)
    if json_key_old is None:
        flash("Symptom not found.")
        return redirect(url_for("admin_dashboard"))

    # keep existing image unless replaced
    image_path = sym_obj.get("img", "")

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            flash("Invalid image type. Allowed: png, jpg, jpeg, webp.")
            return redirect(url_for("admin_dashboard"))

        folder = category_to_folder(new_cat)  # new category folder
        save_dir = os.path.join(UPLOAD_ROOT, folder)
        os.makedirs(save_dir, exist_ok=True)

        ext = image_file.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"{old_id}.{ext}")
        full_path = os.path.join(save_dir, filename)
        image_file.save(full_path)

        image_path = f"images/symptoms/{folder}/{filename}"

    # remove symptom from old category list
    data[json_key_old].pop(idx_old)

    # add into new category list
    json_key_new = CATEGORY_KEYS[new_cat]
    updated = {"id": old_id, "label": new_label}
    if image_path:
        updated["img"] = image_path

    data.setdefault(json_key_new, []).append(updated)

    save_data(data)
    flash(f"Symptom '{old_id}' updated.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)


