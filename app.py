import sqlite3
import streamlit as st
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------------------------------------
# DATABASE SETUP (Using v10 for In-App Shared Downloads)
# ---------------------------------------------------------
DB_NAME = "raut_inventory_v10.db"

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
            item_name TEXT UNIQUE NOT NULL,
            barcode_id TEXT UNIQUE NOT NULL,
            company_name TEXT DEFAULT 'Raut Enterprise'
        )
    """
    )

    # In-App Shared Downloads Table (For Employees to see what was downloaded)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS downloaded_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            barcode_id TEXT NOT NULL,
            company_name TEXT NOT NULL,
            downloaded_by TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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
            ("10 no nut - 1/2 inch", "RT-0000000000001", "Raut Enterprise"),
        )

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

# Helper function to generate barcode image with Product Name printed directly on it using PIL
def generate_custom_barcode_image(item_name, barcode_text, company_name):
    # 1. Generate base barcode using python-barcode
    rv = BytesIO()
    Code128(barcode_text, writer=ImageWriter()).write(rv)
    rv.seek(0)
    
    # 2. Open with PIL to add custom header (Product Name & Company)
    barcode_img = Image.open(rv)
    
    # Create a new canvas with extra space at the top for Product Name & Company
    width, height = barcode_img.size
    new_height = height + 100
    new_img = Image.new("RGB", (width, new_height), "white")
    
    draw = ImageDraw.Draw(new_img)
    
    # Draw Company & Product Name directly onto the image
    try:
        # Using default bitmap font or fallback
        draw.text((15, 10), f"Company: {company_name}", fill="black")
        draw.text((15, 30), f"Product: {item_name}", fill="black")
    except Exception:
        pass
    
    # Paste barcode image below the text
    new_img.paste(barcode_img, (0, 65))
    
    final_io = BytesIO()
    new_img.save(final_io, format="PNG")
    final_io.seek(0)
    return final_io

# Function to generate next sequential barcode like RT-0000000000001
def get_next_barcode_id():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(id) FROM inventory")
    result = c.fetchone()
    conn.close()
    
    next_id = (result[0] or 0) + 1
    return f"RT-{next_id:013d}"

# Function to generate PDF containing the labeled barcode for in-app storage
def generate_barcode_pdf(item_name, barcode_id, company_name):
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>Company:</b> {company_name}", styles['Normal']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Product Name:</b> {item_name}", styles['Heading1']))
    story.append(Spacer(1, 15))

    img_io = generate_custom_barcode_image(item_name, barcode_id, company_name)
    temp_img_path = "temp_custom_barcode.png"
    with open(temp_img_path, "wb") as f:
        f.write(img_io.read())

    story.append(RLImage(temp_img_path, width=320, height=180))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Barcode No: {barcode_id}</b>", styles['Heading2']))

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

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
            [
                "📦 App Barcode Storage", 
                "📂 App Downloaded History", 
                "➕ Generate & Save Barcode", 
                "⚙️ Manage & Edit Inventory", 
                "⚙️ Change Employee Password"
            ]
        )
    else:
        menu = st.sidebar.radio(
            "Navigation", 
            [
                "📦 App Barcode Storage", 
                "📂 App Downloaded History", 
                "➕ Generate & Save Barcode", 
                "⚙️ Manage & Edit Inventory"
            ]
        )

    # --- SECTION 1: APP STORAGE ---
    if menu == "📦 App Barcode Storage":
        st.title("📦 App Central Barcode Storage")
        st.write("Yahan saare saved barcodes hain. Barcode image ke andar hi **Product Name** print dikhega.")
        st.markdown("---")

        conn = get_db_connection()
        df = pd.read_sql_query("SELECT id, item_name, barcode_id, company_name FROM inventory ORDER BY id DESC", conn)
        conn.close()

        if df.empty:
            st.info("App storage mein abhi koi barcode nahi hai.")
        else:
            # CSV Download Button
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Full Inventory as CSV",
                data=csv_data,
                file_name="raut_inventory.csv",
                mime="text/csv",
            )
            st.markdown("---")

            for _, row in df.iterrows():
                item_id = row['id']
                item_name = row['item_name']
                barcode_id = row['barcode_id']
                company_name = row['company_name']

                with st.container():
                    # Display Barcode with Name printed directly on image
                    try:
                        custom_barcode_io = generate_custom_barcode_image(item_name, barcode_id, company_name)
                        st.image(custom_barcode_io, width=350)
                    except Exception as e:
                        st.error(f"Barcode render error: {e}")

                    # Button to save to In-App Shared History (instead of device download)
                    if st.button(f"📥 Save to App Downloads for Employees", key=f"save_app_{item_id}"):
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute(
                                "INSERT INTO downloaded_history (item_name, barcode_id, company_name, downloaded_by) VALUES (?, ?, ?, ?)",
                                (item_name, barcode_id, company_name, st.session_state.username)
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"✅ '{item_name}' ko App Download History mein save kar diya gaya hai! Ab sabhi employees ise dekh sakenge.")
                        except Exception as e:
                            st.error(f"Error: {e}")

                    st.caption(f"Record ID: #{item_id}")
                    st.markdown("---")

    # --- SECTION 2: APP DOWNLOADED HISTORY (For Employees to see) ---
    elif menu == "📂 App Downloaded History":
        st.title("📂 App Downloaded History (Shared with Employees)")
        st.write("Yahan aap aur aapke baki employees dekh sakte hain ki kis-kis product ka barcode download/save kiya gaya hai.")
        st.markdown("---")

        conn = get_db_connection()
        history_df = pd.read_sql_query(
            "SELECT id, item_name, barcode_id, company_name, downloaded_by, timestamp FROM downloaded_history ORDER BY id DESC", 
            conn
        )
        conn.close()

        if history_df.empty:
            st.info("Abhi tak app ke andar koi barcode download/save nahi kiya gaya hai.")
        else:
            for _, row in history_df.iterrows():
                h_id = row['id']
                h_name = row['item_name']
                h_barcode = row['barcode_id']
                h_company = row['company_name']
                h_user = row['downloaded_by']
                h_time = row['timestamp']

                with st.container():
                    st.markdown(f"### 📦 Product: **{h_name}**")
                    st.write(f"**Barcode ID:** `{h_barcode}` | **Company:** {h_company}")
                    st.caption(f"Saved by user: **{h_user}** at {h_time}")
                    
                    # Show the labeled barcode image right here inside the app
                    try:
                        custom_io = generate_custom_barcode_image(h_name, h_barcode, h_company)
                        st.image(custom_io, width=300)
                    except Exception:
                        pass
                    
                    st.markdown("---")

    # --- SECTION 3: GENERATE & SAVE NEW ---
    elif menu == "➕ Generate & Save Barcode":
        st.title("➕ Naya Barcode Generate Karein")
        st.write("Item Name dalein. Duplicate items allowed nahi hain.")

        with st.form("generate_barcode_form"):
            item_name = st.text_input("Item Name", placeholder="e.g. 12 no nut - 1 inch")
            company_name = st.text_input("Company Name", value="Raut Enterprise")
            
            save_btn = st.form_submit_button("Generate & Save to App")

            if save_btn:
                if item_name.strip():
                    auto_barcode_id = get_next_barcode_id()

                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO inventory (item_name, barcode_id, company_name) VALUES (?, ?, ?)",
                            (item_name.strip(), auto_barcode_id, company_name),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Product '{item_name}' aur Barcode '{auto_barcode_id}' successfully save ho gaya hai!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh Product Name pehle se inventory mein saved hai!")
                else:
                    st.warning("Kripya Item Name zaroor bharein.")

    # --- SECTION 4: MANAGE & EDIT ---
    elif menu == "⚙️ Manage & Edit Inventory":
        st.title("⚙️ Manage Inventory (Rename / Delete)")
        st.write("Yahan se aap kisi bhi product ka naam badal (rename) sakte hain ya record delete kar sakte hain.")
        st.markdown("---")

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, item_name, barcode_id FROM inventory ORDER BY id DESC")
        items = c.fetchall()
        conn.close()

        if not items:
            st.info("Manage karne ke liye koi items nahi hain.")
        else:
            item_dict = {f"{item[1]} ({item[2]})": item[0] for item in items}
            selected_item_str = st.selectbox("Select Product to Modify", list(item_dict.keys()))
            selected_id = item_dict[selected_item_str]

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT item_name, barcode_id, company_name FROM inventory WHERE id = ?", (selected_id,))
            curr_name, curr_barcode, curr_company = c.fetchone()
            conn.close()

            with st.form("edit_delete_form"):
                new_name = st.text_input("Rename Product Name", value=curr_name)
                new_company = st.text_input("Company Name", value=curr_company)
                
                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("💾 Save Changes (Rename)")
                with col2:
                    delete_btn = st.form_submit_button("🗑️ Delete Product")

                if update_btn:
                    if new_name.strip():
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute(
                                "UPDATE inventory SET item_name = ?, company_name = ? WHERE id = ?",
                                (new_name.strip(), new_company, selected_id)
                            )
                            conn.commit()
                            conn.close()
                            st.success("✅ Product details successfully updated / renamed!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Yeh product name pehle se exist karta hai.")
                    else:
                        st.warning("Product name khali nahi ho sakta.")

                if delete_btn:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM inventory WHERE id = ?", (selected_id,))
                    conn.commit()
                    conn.close()
                    st.success("🗑️ Product successfully deleted from storage!")
                    st.rerun()

    # --- SECTION 5: CHANGE PASSWORD ---
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
