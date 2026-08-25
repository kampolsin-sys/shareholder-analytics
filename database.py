import os
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib
import streamlit as st

def get_engine():
    db_url = None
    try:
        db_url = st.secrets.get("SUPABASE_DB_URL")
    except Exception:
        pass
        
    if db_url:
        # SQLAlchemy connection string standard
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    
    # Fallback to local SQLite
    return create_engine('sqlite:///shareholders.db')

def init_db():
    engine = get_engine()
    is_postgres = engine.name == 'postgresql'
    
    id_col = "id SERIAL PRIMARY KEY" if is_postgres else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    with engine.begin() as conn:
        # Table for uploaded periods
        conn.execute(text(f'''
            CREATE TABLE IF NOT EXISTS periods (
                {id_col},
                period_name TEXT UNIQUE,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # Table for shareholder data
        conn.execute(text(f'''
            CREATE TABLE IF NOT EXISTS shareholders (
                {id_col},
                period_id INTEGER,
                account_id TEXT,
                holder_type TEXT,
                title_code TEXT,
                grp_id TEXT,
                title TEXT,
                first_name TEXT,
                last_name TEXT,
                total_shares REAL,
                full_name TEXT
                -- FOREIGN KEY (period_id) REFERENCES periods (id) 
                -- Commented out FK to prevent insertion speed issues or strict constraint checks across bulk uploads
            )
        '''))
        # Table for users
        conn.execute(text(f'''
            CREATE TABLE IF NOT EXISTS users (
                {id_col},
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT
            )
        '''))
    
    init_default_admin()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, role='user'):
    username = username.lower()
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)'),
                         {"u": username, "p": hash_password(password), "r": role})
        return True
    except Exception:
        return False

def delete_user(username):
    username = username.lower()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM users WHERE username = :u'), {"u": username})

def get_all_users():
    engine = get_engine()
    return pd.read_sql('SELECT id, username, role FROM users', engine)

def verify_login(username, password):
    username = username.lower()
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text('SELECT password_hash, role FROM users WHERE username = :u'), {"u": username}).fetchone()
    
    if result:
        stored_hash, role = result
        if stored_hash == hash_password(password):
            return True, role
    return False, None

def init_default_admin():
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(text('SELECT COUNT(*) FROM users')).scalar()
        if count == 0:
            with engine.begin() as tx:
                tx.execute(text('INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)'),
                           {"u": 'admin', "p": hash_password('password'), "r": 'admin'})

def add_period(period_name):
    engine = get_engine()
    with engine.begin() as conn:
        # Check if period exists
        res = conn.execute(text('SELECT id FROM periods WHERE period_name = :p'), {"p": period_name}).fetchone()
        if res:
            period_id = res[0]
            # Delete old data
            conn.execute(text('DELETE FROM shareholders WHERE period_id = :pid'), {"pid": period_id})
        else:
            # PostgreSQL requires RETURNING id or fetching max. SQLAlchemy 2.0 returns cursor with last row id differently.
            # Easiest way across dialects:
            conn.execute(text('INSERT INTO periods (period_name) VALUES (:p)'), {"p": period_name})
            period_id = conn.execute(text('SELECT id FROM periods WHERE period_name = :p'), {"p": period_name}).scalar()
            
    return period_id

def save_shareholders_data(df, period_name):
    init_db()
    period_id = add_period(period_name)
    
    # Clean column names (handle TSD export which has English with newline)
    df.columns = [str(c).split('\n')[0].strip() for c in df.columns]
    
    col_mapping = {
        'Account_ID': 'account_id',
        'Holder_Type': 'holder_type',
        'Title Code': 'title_code',
        'Grp_ID': 'grp_id',
        'คำนำหน้าชื่อ': 'title',
        'ชื่อ': 'first_name',
        'นามสกุล /ชื่อบริษัท': 'last_name',
        'จำนวนหุ้นทั้งหมด': 'total_shares',
        'Full_nm': 'full_name',
        
        # TSD Export format
        'เลขทะเบียนผู้ถือหุ้น': 'account_id',
        'ประเภทบุคคล': 'holder_type',
        'จำนวนหุ้น': 'total_shares',
        'รหัสคำนำหน้าชื่อ': 'title_code',
        'นามสกุล': 'last_name'
    }
    
    df_db = df.rename(columns=col_mapping)
    
    if 'full_name' not in df_db.columns:
        t = df_db.get('title', pd.Series(['']*len(df_db))).fillna('')
        f = df_db.get('first_name', pd.Series(['']*len(df_db))).fillna('')
        l = df_db.get('last_name', pd.Series(['']*len(df_db))).fillna('')
        # Construct full name
        df_db['full_name'] = (t + f + ' ' + l).str.replace(r'\s+', ' ', regex=True).str.strip()

    valid_cols = [c for c in set(col_mapping.values()) if c in df_db.columns]
    df_db = df_db[valid_cols]
    df_db['period_id'] = period_id
    
    engine = get_engine()
    df_db.to_sql('shareholders', engine, if_exists='append', index=False, chunksize=10000)

def get_all_periods():
    init_db()
    engine = get_engine()
    return pd.read_sql('SELECT id, period_name FROM periods ORDER BY id DESC', engine)

def get_comparison_data(period_names, min_shares=0, filter_period=None):
    if not period_names:
        return pd.DataFrame()
        
    engine = get_engine()
    
    bind_params = {}
    sum_cols = []
    
    for i, name in enumerate(period_names):
        bind_params[f"p{i}"] = name
        # Use conditional aggregation to pivot rows into columns in SQL
        sum_cols.append(f'SUM(CASE WHEN p.period_name = :p{i} THEN s.total_shares ELSE 0 END) AS "{name}"')
        
    sum_cols_str = ",\n        ".join(sum_cols)
    
    # We must format the IN clause
    bind_names_str = ",".join([f":p{i}" for i in range(len(period_names))])
    
    # Build HAVING clause based on filter_period or any period
    if filter_period and filter_period in period_names:
        idx = period_names.index(filter_period)
        having_clause = f"HAVING SUM(CASE WHEN p.period_name = :p{idx} THEN s.total_shares ELSE 0 END) >= :min_shares"
    else:
        # If no specific filter_period, check if ANY period meets the min_shares
        having_conds = [f"SUM(CASE WHEN p.period_name = :p{i} THEN s.total_shares ELSE 0 END) >= :min_shares" for i in range(len(period_names))]
        having_clause = f"HAVING {' OR '.join(having_conds)}"
        
    bind_params['min_shares'] = min_shares
    
    query = text(f'''
        SELECT s.full_name,
        {sum_cols_str}
        FROM shareholders s
        JOIN periods p ON s.period_id = p.id
        WHERE p.period_name IN ({bind_names_str})
        GROUP BY s.full_name
        {having_clause}
    ''')
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=bind_params)
        
    if df.empty:
        return df
        
    df.set_index('full_name', inplace=True)
    return df

def get_total_shares(period_name):
    engine = get_engine()
    with engine.connect() as conn:
        total = conn.execute(text('''
            SELECT SUM(s.total_shares) 
            FROM shareholders s 
            JOIN periods p ON s.period_id = p.id 
            WHERE p.period_name = :p
        '''), {"p": period_name}).scalar()
    return total if total else 0
