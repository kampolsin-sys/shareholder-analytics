import streamlit as st
import database as db

import os

def login_page():
    logo_path = "logo.png"
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
            
        st.markdown("<h2 style='text-align: center; margin-top: 20px;'>🔒 เข้าสู่ระบบ (Login)</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("ชื่อผู้ใช้ (Username)")
            password = st.text_input("รหัสผ่าน (Password)", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)
            
            if submitted:
                success, role = db.verify_login(username, password)
                if success:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username.lower()
                    st.session_state['role'] = role
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง!")

def admin_page():
    st.header("⚙️ จัดการผู้ใช้งาน (Admin Panel)")
    
    if st.session_state.get('role') != 'admin':
        st.error("คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return
        
    st.subheader("ผู้ใช้งานในระบบ")
    users_df = db.get_all_users()
    st.dataframe(users_df, use_container_width=True, hide_index=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("เพิ่มผู้ใช้งานใหม่")
        with st.form("add_user_form"):
            new_user = st.text_input("ชื่อผู้ใช้ใหม่")
            new_pass = st.text_input("รหัสผ่าน", type="password")
            new_role = st.selectbox("สิทธิ์การใช้งาน (Role)", ["user", "admin"])
            if st.form_submit_button("เพิ่มผู้ใช้งาน"):
                if new_user and new_pass:
                    if db.create_user(new_user, new_pass, new_role):
                        st.success(f"เพิ่มผู้ใช้งาน {new_user} เรียบร้อยแล้ว")
                        st.rerun()
                    else:
                        st.error("ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว")
                else:
                    st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")
                    
    with col2:
        st.subheader("ลบผู้ใช้งาน")
        with st.form("delete_user_form"):
            user_to_delete = st.selectbox("เลือกผู้ใช้งานที่ต้องการลบ", users_df['username'].tolist() if not users_df.empty else [])
            if st.form_submit_button("ลบผู้ใช้งาน"):
                if user_to_delete == 'admin':
                    st.error("ไม่สามารถลบบัญชี admin หลักได้")
                elif user_to_delete == st.session_state['username']:
                    st.error("ไม่สามารถลบบัญชีที่กำลังใช้งานอยู่ได้")
                else:
                    db.delete_user(user_to_delete)
                    st.success(f"ลบผู้ใช้งาน {user_to_delete} เรียบร้อยแล้ว")
                    st.rerun()
