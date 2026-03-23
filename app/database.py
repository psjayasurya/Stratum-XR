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

        conn.commit()
        print("Database initialized successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")


__all__ = ['get_db', 'init_db']
