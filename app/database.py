"""
Database Service
Functions for database connections and operations.
"""
import psycopg2
from app.config import config



def get_db():
    """
    Get PostgreSQL database connection
    
    Returns:
        psycopg2 connection object
    """
    return psycopg2.connect(config.DATABASE_URL)


def init_db():
    """Initialize database tables"""
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        cur = conn.cursor()

        # Add auth hardening columns to users when the table already exists.
        cur.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMP")
        cur.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS otp_attempts INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS otp_last_sent_at TIMESTAMP")
        cur.execute("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        # Create saved_views table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_views (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                view_name VARCHAR(255) NOT NULL,
                job_ids TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create user_profiles table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255) DEFAULT '',
                company_name VARCHAR(255) DEFAULT '',
                photo_url TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create processed_jobs table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_jobs (
                job_id VARCHAR(255) PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                job_name VARCHAR(255) NOT NULL,
                processing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'completed',
                storage_path VARCHAR(255)
            );
        """)
        
        # Create annotations table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id SERIAL PRIMARY KEY,
                job_id VARCHAR(255) NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                ann_type VARCHAR(50) NOT NULL,
                label TEXT DEFAULT '',
                color VARCHAR(20) DEFAULT '#f59e0b',
                note TEXT DEFAULT '',
                positions TEXT NOT NULL DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Index for fast annotation lookups per job
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_annotations_job_user
            ON annotations (job_id, user_email);
        """)

        # Persist per-user cloud mesh geo alignments (keyed by mesh path/name).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_mesh_alignments (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                mesh_key TEXT NOT NULL,
                alignment_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_email, mesh_key)
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_mesh_alignments_user
            ON user_mesh_alignments (user_email);
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_jti VARCHAR(64) PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                token_hash VARCHAR(128) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_agent VARCHAR(255) DEFAULT '',
                ip_address VARCHAR(64) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
            ON auth_sessions (user_email);
        """)

        conn.commit()
        print("Database initialized successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")


__all__ = ['get_db', 'init_db']
