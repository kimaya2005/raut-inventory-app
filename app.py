import sqlite3
import streamlit as st

# ---------------------------------------------------------
# DATABASE SETUP (Using v4 to completely avoid old file conflict)
# ---------------------------------------------------------
DB_NAME = "raut_inventory_v4.db"

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

    # Inventory Table (App internal storage for items and barcodes)
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

    # Sample Data
    c.execute("SELECT * FROM inventory")
    if not c.fetchone():
        c.execute(
            "INSERT INTO inventory (item_name, barcode_id, company_name) VALUES (?, ?, ?)",
            ("10 no nut - 1/2 inch", "RT-000000000001", "Raut Enterprise"),
        )

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

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
        st.write("Jitne bhi Barcodes generate hue hain, sab is app ke andar permanently saved hain.")
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
                    st.subheader(f"📦 {item_name}")
                    st.write(f"**Barcode ID:** `{barcode_id}`")
                    st.write(f"**Company:** {company_name}")
                    st.caption(f"Stored in App Database | Record ID: #{item_id}")
                    st.markdown("---")

    # --- SECTION 2: GENERATE & SAVE ---
    elif menu == "➕ Generate & Save Barcode":
        st.title("➕ Naya Barcode Generate Karein")
        st.write("Yahan naya Item add karke **Save** karein. Yeh sidhe App Storage me save ho jayega.")

        with st.form("generate_barcode_form"):
            item_name = st.text_input("Item Name", placeholder="e.g. 12 no nut - 1 inch")
            barcode_id = st.text_input("Barcode ID", placeholder="e.g. RT-000000000002")
            company_name = st.text_input("Company Name", value="Raut Enterprise")
            
            save_btn = st.form_submit_button("Generate & Save to App")

            if save_btn:
                if item_name and barcode_id:
                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO inventory (item_name, barcode_id, company_name) VALUES (?, ?, ?)",
                            (item_name, barcode_id, company_name),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Barcode '{barcode_id}' app ke storage me successfully save ho gaya hai!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh Barcode ID pehle se App me saved hai. Dusra ID dalein.")
                else:
                    st.warning("Kripya Item Name aur Barcode ID dono bharein.")

    # --- SECTION 3: CHANGE EMPLOYEE PASSWORD ---
    elif menu == "⚙️ Change Employee Password":
        st.title("⚙️ Employee Access Control")
        st.write("Jab koi employee job chhod de, toh yahan se password badal dein taaki purana staff login na kar sake.")
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
