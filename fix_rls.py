import sqlalchemy
from sqlalchemy import text
import os

# Create engine from the URL in app.py/database.py
# Wait, database.py reads from st.secrets. Let's just parse secrets.toml
import toml
secrets = toml.load(".streamlit/secrets.toml")
db_url = secrets["SUPABASE_DB_URL"]

engine = sqlalchemy.create_engine(db_url)

with engine.begin() as conn:
    # Check if tables exist
    tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
    tables = [t[0] for t in tables]
    print("Tables found:", tables)
    
    for table in ["users", "periods", "shareholders"]:
        if table in tables:
            print(f"Enabling RLS on {table}...")
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
    
    print("RLS enabled successfully.")
