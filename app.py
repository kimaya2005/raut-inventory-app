import sqlite3
import streamlit as st
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64
from streamlit.components.v1 import html

# ---------------------------------------------------------
# DATABASE SETUP (Using Permanent DB Name so data NEVER gets deleted)
# ---------------------------------------------------------
DB_NAME = "raut_enterprise_permanent.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            force_logout INTEGER DEFAULT 0
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT UNIQUE NOT NULL,
            barcode_id TEXT UNIQUE NOT NULL,
            price TEXT DEFAULT '',
            slot_category TEXT DEFAULT ''
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS trash_bin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id INTEGER,
            item_name TEXT UNIQUE NOT NULL,
            barcode_id TEXT UNIQUE NOT NULL,
            price TEXT DEFAULT '',
            slot_category TEXT DEFAULT '',
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS downloaded_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            barcode_id TEXT NOT NULL,
            price TEXT DEFAULT '',
            slot_category TEXT DEFAULT '',
            downloaded_by TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action_type TEXT NOT NULL,
            details TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role, force_logout) VALUES (?, ?, ?, ?)",
            ("admin", "raut123", "Admin", 0),
        )

    c.execute("SELECT * FROM users WHERE username = ?", ("employee",))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role, force_logout) VALUES (?, ?, ?, ?)",
            ("employee", "emp123", "Employee", 0),
        )

    c.execute("SELECT * FROM inventory")
    if not c.fetchone():
        c.execute(
            "INSERT INTO inventory (item_name, barcode_id, price, slot_category) VALUES (?, ?, ?, ?)",
            ("10 no nut - 1/2 inch", "0000000000001", "₹50", "Hardware"),
        )

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def log_activity(username, action_type, details):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO activity_logs (username, action_type, details) VALUES (?, ?, ?)",
            (username, action_type, details)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def record_download_history(item_name, barcode_id, username):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT price, slot_category FROM inventory WHERE barcode_id = ?",
            (barcode_id,)
        )
        res = c.fetchone()
        price = res[0] if res else ""
        slot = res[1] if res else ""
        
        c.execute(
            "INSERT INTO downloaded_history (item_name, barcode_id, price, slot_category, downloaded_by) VALUES (?, ?, ?, ?, ?)",
            (item_name, barcode_id, price, slot, username)
        )
        conn.commit()
        conn.close()
        log_activity(username, "DOWNLOAD_PRINT_STICKER", f"Downloaded/Printed sticker for {item_name} ({barcode_id}).")
    except Exception:
        pass

# Helper function: Optimized for 50mm x 37mm thermal stickers with CENTERED product name
def generate_custom_barcode_image(item_name, barcode_text):
    scale = 3  
    
    writer_options = {
        'module_width': 0.35 * scale,
        'module_height': 16.0 * scale,
        'quiet_zone': 8 * scale,
        'write_text': True,
        'font_size': 14 * scale,
        'text_distance': 6.0 * scale
    }

    rv = BytesIO()
    Code128(str(barcode_text), writer=ImageWriter()).write(rv, options=writer_options)
    rv.seek(0)
    
    barcode_img = Image.open(rv)
    bw, bh = barcode_img.size
    
    header_height = 90 * scale
    sticker_width = max(bw + 40 * scale, 520 * scale)
    sticker_height = bh + header_height
    
    sticker_img = Image.new("RGB", (sticker_width, sticker_height), "white")
    draw = ImageDraw.Draw(sticker_img)
    
    font_title = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf"
    ]
    
    for path in font_paths:
        try:
            font_title = ImageFont.truetype(path, 32 * scale)
            break
        except IOError:
            continue
            
    if not font_title:
        try:
            font_title = ImageFont.load_default(size=32 * scale)
        except TypeError:
            font_title = ImageFont.load_default()

    # Calculate exact center for the product name text
    text_to_draw = f"{item_name.upper()}"
    bbox = draw.textbbox((0, 0), text_to_draw, font=font_title)
    text_w = bbox[2] - bbox[0]
    text_x = (sticker_width - text_w) // 2
    text_y = 22 * scale

    draw.text((text_x, text_y), text_to_draw, fill="black", font=font_title)
    
    current_y = 70 * scale
    draw.line([(25 * scale, current_y), (sticker_width - 25 * scale, current_y)], fill="black", width=3 * scale)
    current_y += 15 * scale
    
    x_offset = max(0, (sticker_width - bw) // 2)
    sticker_img.paste(barcode_img, (x_offset, current_y))
    
    final_width = sticker_width // scale
    final_height = sticker_height // scale
    sticker_img = sticker_img.resize((final_width, final_height), Image.Resampling.LANCZOS)
    
    final_io = BytesIO()
    sticker_img.save(final_io, format="PNG")
    final_io.seek(0)
    return final_io

def get_next_barcode_id():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(id) FROM inventory")
    result = c.fetchone()
    c.execute("SELECT MAX(original_id) FROM trash_bin")
    trash_max = c.fetchone()[0] or 0
    conn.close()
    
    max_id = max(result[0] or 0, trash_max)
    next_id = max_id + 1
    return f"{next_id:013d}"

# ---------------------------------------------------------
# SESSION STATE MANAGEMENT
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

if st.session_state.logged_in:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT force_logout FROM users WHERE username = ?", (st.session_state.username,))
    res = c.fetchone()
    conn.close()
    if res and res[0] == 1:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.warning("⚠️ Aapko Admin dwara force logout kar diya gaya hai.")
        st.rerun()

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
            if user:
                username, role = user
                c.execute("UPDATE users SET force_logout = 0 WHERE username = ?", (username,))
                conn.commit()
            conn.close()

            if user:
                username, role = user
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                log_activity(username, "LOGIN", f"User {username} logged in successfully.")
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
        log_activity(st.session_state.username, "LOGOUT", f"User {st.session_state.username} logged out.")
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()

    if st.session_state.role == "Admin":
        menu = st.sidebar.radio(
            "Navigation", 
            [
                "📊 Inventory Dashboard",
                "📦 App Barcode Storage", 
                "🖨️ Direct Print / Download 50x37mm",
                "📂 App Downloaded History", 
                "♻️ Trash / Bin Folder", 
                "📜 Activity Audit Logs",
                "➕ Generate & Save Barcode", 
                "⚙️ Manage & Edit Inventory", 
                "⚙️ Manage Employee Access"
            ]
        )
    else:
        menu = st.sidebar.radio(
            "Navigation", 
            [
                "📊 Inventory Dashboard",
                "📦 App Barcode Storage", 
                "🖨️ Direct Print / Download 50x37mm",
                "📂 App Downloaded History", 
                "♻️ Trash / Bin Folder", 
                "➕ Generate & Save Barcode", 
                "⚙️ Manage & Edit Inventory"
            ]
        )

    # --- SECTION 0: INVENTORY DASHBOARD ---
    if menu == "📊 Inventory Dashboard":
        st.title("📊 Raut Enterprise - Summary Dashboard")
        st.write("Yahan aapko poori inventory ka quick overview mil jayega.")
        st.markdown("---")

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM inventory")
        total_inv = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM trash_bin")
        total_trash = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM downloaded_history")
        total_history = c.fetchone()[0]
        conn.close()

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.metric(label="📦 Active Products", value=total_inv)
        with col_d2:
            st.metric(label="♻️ Items in Trash", value=total_trash)
        with col_d3:
            st.metric(label="📥 Downloaded Records", value=total_history)

        st.markdown("---")
        st.subheader("💡 Quick Actions & CSV Export")
        
        conn = get_db_connection()
        full_df = pd.read_sql_query("SELECT id, item_name, barcode_id, price, slot_category FROM inventory ORDER BY id DESC", conn)
        conn.close()

        if not full_df.empty:
            csv_export = full_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Full Inventory CSV Report",
                data=csv_export,
                file_name="raut_full_inventory_report.csv",
                mime="text/csv",
            )
        else:
            st.info("Export karne ke liye inventory mein koi items nahi hain.")

    # --- SECTION 1: APP STORAGE WITH SEARCH BAR ---
    elif menu == "📦 App Barcode Storage":
        st.title("📦 App Central Barcode Storage")
        st.write("Yahan saare saved barcodes 100% scanner-friendly pure numeric format mein hain.")
        st.markdown("---")

        search_query = st.text_input("🔍 Search Products (Type Item Name or Barcode ID)...", "").strip().lower()

        conn = get_db_connection()
        if search_query:
            query = "SELECT id, item_name, barcode_id, price, slot_category FROM inventory WHERE LOWER(item_name) LIKE ? OR barcode_id LIKE ? ORDER BY id DESC"
            df = pd.read_sql_query(query, conn, params=(f"%{search_query}%", f"%{search_query}%"))
        else:
            df = pd.read_sql_query("SELECT id, item_name, barcode_id, price, slot_category FROM inventory ORDER BY id DESC", conn)
        conn.close()

        if df.empty:
            st.info("Koi matching barcode nahi mila.")
        else:
            col_exp1, _ = st.columns(2)
            with col_exp1:
                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Filtered List as CSV",
                    data=csv_data,
                    file_name="raut_filtered_inventory.csv",
                    mime="text/csv",
                )
            st.markdown("---")

            for _, row in df.iterrows():
                item_id = row['id']
                item_name = row['item_name']
                barcode_id = row['barcode_id']
                price = row['price']
                slot_category = row['slot_category']

                with st.container():
                    try:
                        custom_barcode_io = generate_custom_barcode_image(item_name, barcode_id)
                        st.image(custom_barcode_io, width=320)
                    except Exception as e:
                        st.error(f"Barcode render error: {e}")

                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button(f"📥 Save to App History", key=f"save_app_{item_id}"):
                            record_download_history(item_name, barcode_id, st.session_state.username)
                            st.success(f"✅ App History mein save ho gaya!")

                    with col2:
                        try:
                            local_img_io = generate_custom_barcode_image(item_name, barcode_id)
                            if st.download_button(
                                label="💾 Download PNG File",
                                data=local_img_io,
                                file_name=f"{item_name}_{barcode_id}.png",
                                mime="image/png",
                                key=f"download_device_{item_id}"
                            ):
                                record_download_history(item_name, barcode_id, st.session_state.username)
                        except Exception as e:
                            st.error(f"Download error: {e}")

                    st.caption(f"Record ID: #{item_id} | Price: {price or 'N/A'} | Slot/Cat: {slot_category or 'N/A'}")
                    st.markdown("---")

    # --- SECTION 1.5: DIRECT PRINT & DOWNLOAD 50x37mm STICKER ---
    elif menu == "🖨️ Direct Print / Download 50x37mm":
        st.title("🖨️ Direct Print & Download 50mm x 37mm Thermal Sticker")
        st.write("Yahan se aap exact 50mm x 37mm size mein sticker download ya direct print kar sakte hain.")
        st.markdown("---")

        conn = get_db_connection()
        p_df = pd.read_sql_query("SELECT id, item_name, barcode_id FROM inventory ORDER BY id DESC", conn)
        conn.close()

        if p_df.empty:
            st.info("Print karne ke liye koi products nahi hain.")
        else:
            item_dict_p = {f"{row['item_name'].upper()} (ID: {row['barcode_id']})": (row['item_name'], row['barcode_id']) for _, row in p_df.iterrows()}
            selected_p_str = st.selectbox("Select Product", list(item_dict_p.keys()))
            p_name, p_barcode = item_dict_p[selected_p_str]

            st.markdown("### 🏷️ Sticker Preview (50mm x 37mm - Centered Name)")
            try:
                single_img_io = generate_custom_barcode_image(p_name, p_barcode)
                st.image(single_img_io, width=320)
                
                st.markdown("---")
                
                col_opt1, col_opt2 = st.columns(2)
                
                with col_opt1:
                    if st.download_button(
                        label="💾 Download to Computer",
                        data=single_img_io,
                        file_name=f"Sticker_{p_name}_{p_barcode}.png",
                        mime="image/png",
                        type="secondary"
                    ):
                        record_download_history(p_name, p_barcode, st.session_state.username)
                
                with col_opt2:
                    img_bytes = single_img_io.getvalue()
                    encoded_img = base64.b64encode(img_bytes).decode('utf-8')

                    print_script_html = f"""
                    <html>
                    <head>
                        <style>
                            @page {{ size: 50mm 37mm; margin: 0; }}
                            body {{ margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; background: white; }}
                            img {{ width: 50mm; height: 37mm; object-fit: contain; }}
                        </style>
                    </head>
                    <body>
                        <img id="print_img" src="data:image/png;base64,{encoded_img}" />
                        <script>
                            document.getElementById('print_img').onload = function() {{
                                window.print();
                            }};
                        </script>
                    </body>
                    </html>
                    """
                    
                    if st.button("🖨️ Direct Print via Printer", type="primary"):
                        record_download_history(p_name, p_barcode, st.session_state.username)
                        html(print_script_html, height=120)
                        st.success("✅ Print dialog trigger ho gaya hai aur history mein record ho gaya hai!")

                st.info("💡 **Note:** Product name ab bilkul center mein aayega!")

            except Exception as e:
                st.error(f"Error: {e}")

    # --- SECTION 2: APP DOWNLOADED HISTORY ---
    elif menu == "📂 App Downloaded History":
        st.title("📂 App Downloaded & Printed History")
        st.write("Yahan aap aur aapke employees dekh sakte hain ki kisne kaunsa barcode download ya print kiya hai.")
        st.markdown("---")

        conn = get_db_connection()
        history_df = pd.read_sql_query(
            "SELECT id, item_name, barcode_id, price, slot_category, downloaded_by, timestamp FROM downloaded_history ORDER BY id DESC", 
            conn
        )
        conn.close()

        if history_df.empty:
            st.info("Abhi tak app ke andar koi barcode download ya print nahi kiya gaya hai.")
        else:
            hist_csv = history_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Download History CSV",
                data=hist_csv,
                file_name="download_history.csv",
                mime="text/csv"
            )
            st.markdown("---")

            for _, row in history_df.iterrows():
                h_id = row['id']
                h_name = row['item_name']
                h_barcode = row['barcode_id']
                h_price = row['price']
                h_slot = row['slot_category']
                h_user = row['downloaded_by']
                h_time = row['timestamp']

                with st.container():
                    st.markdown(f"### 📦 Product: **{h_name}**")
                    st.write(f"**Barcode ID:** `{h_barcode}` | **Price:** {h_price or 'N/A'} | **Slot/Cat:** {h_slot or 'N/A'}")
                    st.caption(f"Action performed by user: **{h_user}** at {h_time}")
                    
                    try:
                        custom_io = generate_custom_barcode_image(h_name, h_barcode)
                        st.image(custom_io, width=280)
                    except Exception:
                        pass
                    
                    st.markdown("---")

    # --- SECTION 3: TRASH / BIN FOLDER ---
    elif menu == "♻️ Trash / Bin Folder":
        st.title("♻️ Trash / Bin Folder (Deleted Items)")
        st.write("Agar koi product galti se delete ho gaya ho, toh aap use yahan se wapas **Restore** kar sakte hain.")
        st.markdown("---")

        conn = get_db_connection()
        trash_df = pd.read_sql_query("SELECT id, original_id, item_name, barcode_id, price, slot_category, deleted_at FROM trash_bin ORDER BY id DESC", conn)
        conn.close()

        if trash_df.empty:
            st.info("Trash bin bilkul khali hai.")
        else:
            for _, row in trash_df.iterrows():
                t_id = row['id']
                orig_id = row['original_id']
                t_name = row['item_name']
                t_barcode = row['barcode_id']
                t_price = row['price']
                t_slot = row['slot_category']
                t_time = row['deleted_at']

                with st.container():
                    st.markdown(f"### 🗑️ Deleted Product: **{t_name}**")
                    st.write(f"**Barcode ID:** `{t_barcode}` | **Price:** {t_price or 'N/A'} | **Slot/Cat:** {t_slot or 'N/A'}")
                    st.caption(f"Deleted at: {t_time}")

                    try:
                        custom_io = generate_custom_barcode_image(t_name, t_barcode)
                        st.image(custom_io, width=280)
                    except Exception:
                        pass

                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        if st.button(f"♻️ Restore Product", key=f"restore_{t_id}"):
                            try:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute(
                                    "INSERT INTO inventory (id, item_name, barcode_id, price, slot_category) VALUES (?, ?, ?, ?, ?)",
                                    (orig_id, t_name, t_barcode, t_price, t_slot)
                                )
                                c.execute("DELETE FROM trash_bin WHERE id = ?", (t_id,))
                                conn.commit()
                                conn.close()
                                log_activity(st.session_state.username, "RESTORE", f"Restored product {t_name} from trash.")
                                st.success(f"✅ Product '{t_name}' successfully restore ho gaya hai!")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                try:
                                    c.execute(
                                        "INSERT INTO inventory (item_name, barcode_id, price, slot_category) VALUES (?, ?, ?, ?)",
                                        (t_name, t_barcode, t_price, t_slot)
                                    )
                                    c.execute("DELETE FROM trash_bin WHERE id = ?", (t_id,))
                                    conn.commit()
                                    conn.close()
                                    log_activity(st.session_state.username, "RESTORE", f"Restored product {t_name} from trash.")
                                    st.success(f"✅ Product '{t_name}' successfully restore ho gaya hai!")
                                    st.rerun()
                                except Exception as err:
                                    conn.close()
                                    st.error(f"Restore error: {err}")
                            except Exception as e:
                                st.error(f"Error: {e}")

                    with col_r2:
                        if st.button(f"🔥 Delete Permanently", key=f"perm_del_{t_id}"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("DELETE FROM trash_bin WHERE id = ?", (t_id,))
                            conn.commit()
                            conn.close()
                            log_activity(st.session_state.username, "PERM_DELETE", f"Permanently deleted product {t_name}.")
                            st.success(f"🔥 Product permanently delete ho gaya.")
                            st.rerun()

                    st.markdown("---")

    # --- SECTION 4: ACTIVITY AUDIT LOGS (Admin Only) ---
    elif menu == "📜 Activity Audit Logs" and st.session_state.role == "Admin":
        st.title("📜 Team Activity Audit Logs")
        st.write("Yahan aap dekh sakte hain ki kis user ne kab kaunsa action perform kiya hai.")
        st.markdown("---")

        conn = get_db_connection()
        logs_df = pd.read_sql_query("SELECT id, username, action_type, details, timestamp FROM activity_logs ORDER BY id DESC", conn)
        conn.close()

        if logs_df.empty:
            st.info("Abhi tak koi activity record nahi hai.")
        else:
            log_csv = logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Activity Logs CSV",
                data=log_csv,
                file_name="activity_audit_logs.csv",
                mime="text/csv"
            )
            st.markdown("---")
            st.dataframe(logs_df, use_container_width=True)

    # --- SECTION 5: GENERATE & SAVE NEW ---
    elif menu == "➕ Generate & Save Barcode":
        st.title("➕ Naya Barcode Generate Karein")
        st.write("Item Name zaroori hai. Price aur Slot/Category optional hain (agar nahi chahiye toh khali chhod dein).")

        with st.form("generate_barcode_form"):
            item_name = st.text_input("Item Name (Required)", placeholder="e.g. 12 no nut - 1 inch")
            
            col_p, col_s = st.columns(2)
            with col_p:
                price_input = st.text_input("Price (Optional)", placeholder="e.g. ₹150")
            with col_s:
                slot_input = st.text_input("Slot / Category (Optional)", placeholder="e.g. Rack A-3 / Hardware")
            
            save_btn = st.form_submit_button("Generate & Save to App")

            if save_btn:
                if item_name.strip():
                    clean_name = item_name.strip()
                    conn = get_db_connection()
                    c = conn.cursor()
                    
                    c.execute("SELECT barcode_id, price, slot_category FROM inventory WHERE item_name = ?", (clean_name,))
                    existing_item = c.fetchone()
                    
                    if existing_item:
                        conn.close()
                        st.warning(f"⚠️ Yeh Product Name pehle se inventory mein saved hai! Neeche existing barcode ki details dekhein:")
                        ex_barcode = existing_item[0]
                        
                        try:
                            ex_img_io = generate_custom_barcode_image(clean_name, ex_barcode)
                            st.image(ex_img_io, width=320)
                            if st.download_button(
                                label="💾 Download Sticker PNG",
                                data=ex_img_io,
                                file_name=f"{clean_name}_{ex_barcode}.png",
                                mime="image/png"
                            ):
                                record_download_history(clean_name, ex_barcode, st.session_state.username)
                        except Exception as e:
                            st.error(f"Error rendering barcode: {e}")
                    else:
                        auto_barcode_id = get_next_barcode_id()
                        try:
                            c.execute(
                                "INSERT INTO inventory (item_name, barcode_id, price, slot_category) VALUES (?, ?, ?, ?)",
                                (clean_name, auto_barcode_id, price_input.strip(), slot_input.strip()),
                            )
                            conn.commit()
                            conn.close()
                            log_activity(st.session_state.username, "CREATE", f"Created product {clean_name} with ID {auto_barcode_id}.")
                            st.success(f"✅ Product '{clean_name}' aur Barcode '{auto_barcode_id}' successfully save ho gaya hai!")
                            st.rerun()
                        except Exception as e:
                            conn.close()
                            st.error(f"Error: {e}")
                else:
                    st.warning("Kripya Item Name zaroor bharein.")

    # --- SECTION 6: MANAGE & EDIT ---
    elif menu == "⚙️ Manage & Edit Inventory":
        st.title("⚙️ Manage Inventory (Rename / Edit / Delete)")
        st.write("Yahan se aap kisi bhi product ka naam, price ya slot badal sakte hain, ya delete karke Trash mein bhej sakte hain.")
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
            c.execute("SELECT item_name, barcode_id, price, slot_category FROM inventory WHERE id = ?", (selected_id,))
            curr_name, curr_barcode, curr_price, curr_slot = c.fetchone()
            conn.close()

            with st.form("edit_delete_form"):
                new_name = st.text_input("Rename Product Name", value=curr_name)
                new_price = st.text_input("Update Price", value=curr_price)
                new_slot = st.text_input("Update Slot / Category", value=curr_slot)
                
                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("💾 Save Changes")
                with col2:
                    delete_btn = st.form_submit_button("🗑️ Move to Trash")

                if update_btn:
                    if new_name.strip():
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute(
                                "UPDATE inventory SET item_name = ?, price = ?, slot_category = ? WHERE id = ?",
                                (new_name.strip(), new_price.strip(), new_slot.strip(), selected_id)
                            )
                            conn.commit()
                            conn.close()
                            log_activity(st.session_state.username, "UPDATE", f"Updated product details for ID {selected_id}.")
                            st.success(f"✅ Product details successfully updated!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Yeh product name pehle se exist karta hai.")
                    else:
                        st.warning("Product name khali nahi ho sakta.")

                if delete_btn:
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        c.execute(
                            "INSERT INTO trash_bin (original_id, item_name, barcode_id, price, slot_category) VALUES (?, ?, ?, ?, ?)",
                            (selected_id, curr_name, curr_barcode, curr_price, curr_slot)
                        )
                        c.execute("DELETE FROM inventory WHERE id = ?", (selected_id,))
                        conn.commit()
                        conn.close()
                        log_activity(st.session_state.username, "MOVE_TO_TRASH", f"Moved product {curr_name} to trash.")
                        st.success(f"🗑️ Product successfully Trash folder mein bhej diya gaya hai!")
                        st.rerun()
                    except Exception as e:
                        conn.close()
                        st.error(f"Error moving to trash: {e}")

    # --- SECTION 7: MANAGE EMPLOYEE ACCESS & FORCE LOGOUT ---
    elif menu == "⚙️ Manage Employee Access" and st.session_state.role == "Admin":
        st.title("⚙️ Employee Access Control & Force Logout")
        st.write("Yahan se aap employee ka password badal sakte hain ya unhe force-logout kar sakte hain.")
        st.markdown("---")

        st.subheader("🔑 Change Employee Password")
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
                    log_activity(st.session_state.username, "CHANGE_PASSWORD", "Updated employee password.")
                    st.success(f"✅ Employee ka password badal diya gaya hai!")
                else:
                    st.warning("Naya password enter karein.")

        st.markdown("---")
        st.subheader("🚪 Force Logout Employee")
        st.write("Agar employee login karke chhod gaya hai, toh aap yahan click karke use turant log out kar sakte hain.")
        
        if st.button("🚨 Force Logout Employee Now"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE users SET force_logout = 1 WHERE username = 'employee'")
            conn.commit()
            conn.close()
            log_activity(st.session_state.username, "FORCE_LOGOUT", "Admin force-logged out the employee.")
            st.success("✅ Employee ko successfully force logout kar diya gaya hai!")
