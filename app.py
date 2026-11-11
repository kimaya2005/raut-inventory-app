import sqlite3
import streamlit as st
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# ---------------------------------------------------------
# DATABASE SETUP (Using v6 for Sequential 13-Digit Barcodes)
# ---------------------------------------------------------
DB_NAME = "raut_inventory_v6.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users Table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """
    )

    # Inventory Table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            barcode_id TEXT UNIQUE NOT NULL,
            company_name TEXT DEFAULT 'Raut Enterprise'
        )
    """
    )

    # Admin Account
    c.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "raut123", "Admin"),
        )

    # Shared Employee Account
    c.execute("SELECT * FROM users WHERE username = ?", ("employee",))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("employee", "emp123", "Employee"),
        )

    # Sample Data (13-digit sequential format)
    c.execute("SELECT * FROM inventory")
    if not c.fetchone():
        c.execute(
            "INSERT INTO inventory (item_name, barcode_id, company_name) VALUES (?, ?, ?)",
            ("10 no nut - 1/2 inch", "0000000000001", "Raut Enterprise"),
        )

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

# Helper function to generate automatic barcode image
def generate_barcode_image(barcode_text):
    rv = BytesIO()
    Code128(barcode_text, writer=ImageWriter()).write(rv)
    rv.seek(0)
    return rv

# Function to generate next 13-digit sequential barcode
def get_next_barcode_id():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(id) FROM inventory")
    result = c.fetchone()
    conn.close()
    
    next_id = (result[0] or 0) + 1
    # Format as 13 digits with leading zeros (e.g., 0000000000001)
    return f"{next_id:013d}"

# ---------------------------------------------------------
# SESSION STATE MANAGEMENT
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

# ---------------------------------------------------------
# LOGIN SCREEN
# ---------------------------------------------------------
if not st.session_state.logged_in:
    st.title("🔐 Raut Enterprise - Login")
    st.write("Apna Username aur Password darj karke login karein.")

    with st.form("login_form"):
        u_input = st.text_input("Username")
        p_input = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Login")

        if submit_btn:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(
                "SELECT username, role FROM users WHERE username = ? AND password = ?",
                (u_input, p_input),
            )
            user = c.fetchone()
            conn.close()

            if user:
                username, role = user
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error("❌ Galat Username ya Password!")

# ---------------------------------------------------------
# MAIN APPLICATION WORKFLOW
# ---------------------------------------------------------
else:
    st.sidebar.title("Raut Enterprise")
    st.sidebar.write(f"Logged in: **{st.session_state.username}** ({st.session_state.role})")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()

    # Admin and Employee Navigation
    if st.session_state.role == "Admin":
        menu = st.sidebar.radio(
            "Navigation", 
            ["📦 App Barcode Storage", "➕ Generate & Save Barcode", "⚙️ Change Employee Password"]
        )
    else:
        menu = st.sidebar.radio(
            "Navigation", 
            ["📦 App Barcode Storage", "➕ Generate & Save Barcode"]
        )

    # --- SECTION 1: APP STORAGE ---
    if menu == "📦 App Barcode Storage":
        st.title("📦 App Central Barcode Storage")
        st.write("Yahan sabhi items ke barcodes dekh sakte hain. Barcode ke upar **Product Name** aur niche **13-Digit Barcode Number** bold mein dikhega.")
        st.markdown("---")

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, item_name, barcode_id, company_name FROM inventory ORDER BY id DESC")
        items = c.fetchall()
        conn.close()

        if not items:
            st.info("App storage mein abhi koi barcode nahi hai.")
        else:
            for item_id, item_name, barcode_id, company_name in items:
                with st.container():
                    # Product name bold above barcode
                    st.markdown(f"### 📦 Product: **{item_name}**")
                    st.write(f"Company: {company_name}")
                    
                    # Generate and display barcode image
                    try:
                        barcode_io = generate_barcode_image(barcode_id)
                        st.image(barcode_io, width=300)
                    except Exception as e:
                        st.error(f"Barcode render error: {e}")

                    # Barcode number bold below image
                    st.markdown(f"**Barcode No: `{barcode_id}`**")
                    st.caption(f"Record ID: #{item_id}")
                    st.markdown("---")

    # --- SECTION 2: GENERATE & SAVE (Sequential 13-Digit Barcode) ---
    elif menu == "➕ Generate & Save Barcode":
        st.title("➕ Naya Barcode Generate Karein")
        st.write("Sirf **Item Name** likhein, agla sequential 13-digit barcode automatic assign ho jayega.")

        with st.form("generate_barcode_form"):
            item_name = st.text_input("Item Name", placeholder="e.g. 12 no nut - 1 inch")
            company_name = st.text_input("Company Name", value="Raut Enterprise")
            
            save_btn = st.form_submit_button("Generate & Save to App")

            if save_btn:
                if item_name:
                    # Get next sequential 13-digit barcode
                    auto_barcode_id = get_next_barcode_id()

                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO inventory (item_name, barcode_id, company_name) VALUES (?, ?, ?)",
                            (item_name, auto_barcode_id, company_name),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Product '{item_name}' aur 13-digit Barcode '{auto_barcode_id}' successfully save ho gaya hai!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh Barcode ID pehle se exist karti hai. Dobara try karein.")
                else:
                    st.warning("Kripya Item Name zaroor bharein.")

    # --- SECTION 3: CHANGE EMPLOYEE PASSWORD ---
    elif menu == "⚙️ Change Employee Password":
        st.title("⚙️ Employee Access Control")
        st.write("Jab koi employee job chhod de, toh yahan se password badal dein.")
        st.markdown("---")

        with st.form("change_pass_form"):
            new_emp_pass = st.text_input("Naya Employee Password", type="password")
            update_btn = st.form_submit_button("Update Password")

            if update_btn:
                if new_emp_pass:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute(
                        "UPDATE users SET password = ? WHERE username = 'employee'",
                        (new_emp_pass,),
                    )
                    conn.commit()
                    conn.close()
                    st.success("✅ Employee ka password badal diya gaya hai!")
                else:
                    st.warning("Naya password enter karein.")
