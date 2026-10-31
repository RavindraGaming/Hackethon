import streamlit as st
import sqlite3
import os
from pathlib import Path
from datetime import datetime

# Database and file storage configuration
DB_FILE = "database.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Campus Lost & Found", layout="wide", page_icon="🔎")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,         -- 'Lost' or 'Found'
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            date_logged TEXT NOT NULL,
            contact TEXT NOT NULL,
            description TEXT NOT NULL,
            image_path TEXT,
            is_resolved INTEGER DEFAULT 0 -- 0: Active, 1: Resolved/Claimed
        )
    ''')
    conn.commit()

    # Pre-seed items on initial launch
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] == 0:
        seed_sample_data(c)
        conn.commit()
    conn.close()

def seed_sample_data(cursor):
    """Seed the requested sample items along with counterpart matches."""
    sample_records = [
        # Requested Item 1: Blue Water Bottle (Lost)
        ("Lost", "Blue Water Bottle", "Personal Item", "Library", 
         "2026-10-31 09:30", "student.arun@campus.edu", 
         "Metallic blue insulated water bottle with a small dent on the steel cap.", 
         "uploads/bottle.jpg"),

        # Counterpart Match for Item 1 (Found)
        ("Found", "Blue Metal Water Bottle", "Personal Item", "Library 2nd Floor", 
         "2026-10-31 11:15", "library.desk@campus.edu", 
         "Found blue insulated water bottle left near study tables.", 
         "uploads/bottle.jpg"),

        # Requested Item 2: Black Headphones (Found)
        ("Found", "Black Headphones", "Electronics", "Canteen", 
         "2026-10-30 14:00", "canteen.manager@campus.edu", 
         "Found black over-ear wireless noise cancelling headphones in carrying pouch.", 
         "uploads/headphones.jpg"),

        # Counterpart Match for Item 2 (Lost)
        ("Lost", "Black Sony Headphones", "Electronics", "Canteen Table 4", 
         "2026-10-30 12:45", "+91 98765 43210", 
         "Lost my black wireless over-ear headphones while having lunch.", 
         "uploads/headphones.jpg"),

        # Requested Item 3: Student ID Card (Found)
        ("Found", "Student ID Card", "Documents", "Block A", 
         "2026-10-31 10:00", "admin.office@campus.edu", 
         "Student identity card belonging to Priya Sharma picked up near Block A stairs.", 
         "uploads/id_card.png")
    ]
    cursor.executemany('''
        INSERT INTO items (status, title, category, location, date_logged, contact, description, image_path, is_resolved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', sample_records)

def reset_database():
    """Allows instant wipe and re-seeding between live demonstrations."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS items")
    conn.commit()
    conn.close()
    init_db()

init_db()

# Database operations
def add_item(status, title, category, location, contact, description, image_file):
    image_rel_path = ""
    if image_file:
        unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.name}"
        save_path = UPLOAD_DIR / unique_name
        with open(save_path, "wb") as f:
            f.write(image_file.getbuffer())
        image_rel_path = str(save_path)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO items (status, title, category, location, date_logged, contact, description, image_path, is_resolved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (status, title, category, location, datetime.now().strftime("%Y-%m-%d %H:%M"), contact, description, image_rel_path))
    conn.commit()
    conn.close()

def get_items(status=None, category=None, search_term=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = "SELECT id, status, title, category, location, date_logged, contact, description, image_path, is_resolved FROM items WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if search_term:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ?)"
        wildcard = f"%{search_term}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def resolve_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE items SET is_resolved = 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def find_matches(item_id):
    """Matches opposite reports (Lost vs Found) that share the same category and keywords."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT status, category, title, description FROM items WHERE id = ?", (item_id,))
    target = c.fetchone()
    if not target:
        conn.close()
        return []

    target_status, target_cat, target_title, target_desc = target
    opposite_status = "Found" if target_status == "Lost" else "Lost"

    c.execute("""
        SELECT id, title, location, date_logged, contact, description, image_path 
        FROM items 
        WHERE status = ? AND category = ? AND is_resolved = 0
    """, (opposite_status, target_cat))
    candidates = c.fetchall()
    conn.close()

    target_words = set((target_title + " " + target_desc).lower().split())
    matches = []
    for cand in candidates:
        cand_id, cand_title, cand_loc, cand_date, cand_contact, cand_desc, cand_img = cand
        cand_words = set((cand_title + " " + cand_desc).lower().split())
        overlap = {w for w in target_words.intersection(cand_words) if len(w) > 3}
        if len(overlap) >= 1:
            matches.append({
                "id": cand_id,
                "title": cand_title,
                "location": cand_loc,
                "date": cand_date,
                "contact": cand_contact,
                "desc": cand_desc,
                "image": cand_img,
                "matched_keywords": list(overlap),
                "score": len(overlap)
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches

# Categories and layout
CATEGORIES = ["Personal Item", "Electronics", "Documents", "Keys", "Bags / Backpacks", "Clothing", "Other"]

with st.sidebar:
    st.header("⚙️ Hackathon Demo Controls")
    st.caption("Reset to original clean sample data anytime:")
    if st.button("🔄 Reset Demo Data"):
        reset_database()
        st.success("Database restored to demo samples!")
        st.rerun()

st.title("🔎 Campus Lost & Found Hub")
st.write("An automated digital platform connecting lost items with found reports.")

tab_feed, tab_report, tab_match = st.tabs(["📋 Item Listings", "➕ Report an Item", "⚡ Smart Match Finder"])

# Tab 1: Listings with visual photo rendering
with tab_feed:
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_status = st.selectbox("Status Filter", ["All", "Lost", "Found"])
    with col_f2:
        filter_category = st.selectbox("Category Filter", ["All"] + CATEGORIES)
    with col_f3:
        search_query = st.text_input("Keywords Search", placeholder="e.g. bottle, canteen, headphones")

    items = get_items(filter_status, filter_category, search_query)

    if not items:
        st.info("No matching lost or found records.")
    else:
        for itm in items:
            item_id, status, title, category, location, date_logged, contact, description, img_path, is_resolved = itm
            status_color = "red" if status == "Lost" else "green"
            
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                with c1:
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                    else:
                        st.caption("📷 No image provided")
                with c2:
                    st.markdown(f"### :{status_color}[[{status.upper()}]] {title}")
                    st.write(f"**Category:** `{category}` | **Location:** {location} | **Reported:** {date_logged}")
                    st.write(f"**Description:** {description}")
                    st.write(f"**Contact:** `{contact}`")
                    
                    if is_resolved:
                        st.success("✅ Resolved / Claimed")
                    else:
                        if st.button("Mark as Claimed", key=f"res_{item_id}"):
                            resolve_item(item_id)
                            st.rerun()

# Tab 2: Report an Item (Form input + Photo upload)
with tab_report:
    st.subheader("Submit a Lost or Found Report")
    with st.form("report_form", clear_on_submit=True):
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            status_input = st.radio("Type of Report *", ["Lost", "Found"], horizontal=True)
            title_input = st.text_input("Item Name / Title *", placeholder="e.g., Blue Water Bottle")
            category_input = st.selectbox("Category *", CATEGORIES)
        with col_r2:
            location_input = st.text_input("Location *", placeholder="e.g., Library, Canteen, Block A")
            contact_input = st.text_input("Contact Email / Phone *", placeholder="student@campus.edu")
            image_input = st.file_uploader("Upload Image (Optional)", type=["png", "jpg", "jpeg"])

        description_input = st.text_area("Detailed Description *", placeholder="Mention colors, brand names, scratch marks, stickers...")
        submit = st.form_submit_button("Publish Report", type="primary")

        if submit:
            if not title_input.strip() or not location_input.strip() or not contact_input.strip() or not description_input.strip():
                st.error("Please fill in all mandatory fields marked with *.")
            else:
                add_item(status_input, title_input, category_input, location_input, contact_input, description_input, image_input)
                st.success("Item successfully logged into the database!")

# Tab 3: Smart Match Finder Engine
with tab_match:
    st.subheader("⚡ Automated Smart Match Finder")
    st.write("Select an unresolved report to scan for counterpart matches using category and descriptive tokens.")

    active_records = [i for i in get_items("All", "All") if i[9] == 0]
    
    if not active_records:
        st.info("No active open reports to match right now.")
    else:
        select_dict = {f"#{i[0]} [{i[1]}] {i[2]} ({i[3]})": i[0] for i in active_records}
        user_select = st.selectbox("Choose a report to evaluate:", list(select_dict.keys()))
        selected_id = select_dict[user_select]

        if st.button("Run Smart Matcher", type="primary"):
            matches = find_matches(selected_id)
            if not matches:
                st.warning("No potential matches found with similar category and keywords.")
            else:
                st.success(f"Discovered {len(matches)} potential match candidate(s)!")
                for m in matches:
                    with st.container(border=True):
                        m1, m2 = st.columns([1, 4])
                        with m1:
                            if m["image"] and os.path.exists(m["image"]):
                                st.image(m["image"], use_container_width=True)
                            else:
                                st.caption("📷 No image")
                        with m2:
                            st.markdown(f"#### Match #{m['id']}: {m['title']}")
                            st.write(f"**Found at:** {m['location']} | **Date:** {m['date']}")
                            st.write(f"**Description:** {m['desc']}")
                            st.write(f"**Matching Tokens:** " + " ".join([f"`{w}`" for w in m['matched_keywords']]))
                            st.write(f"**Finder/Owner Contact:** `{m['contact']}`")