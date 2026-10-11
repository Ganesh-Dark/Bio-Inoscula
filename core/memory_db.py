import sqlite3
import os

# Connect to the database in the root folder
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bioweaver_memory.db")

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Episodic memory table for sliding window chat history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            message TEXT
        )
    """)
    
    # Semantic memory table for permanent facts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT UNIQUE
        )
    """)
    
    conn.commit()
    conn.close()

def save_message(role: str, message: str):
    """Saves a single message (user or AI) to the episodic memory."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO episodic_memory (role, message) VALUES (?, ?)", (role, message))
    conn.commit()
    conn.close()

def get_recent_messages(limit: int = 10):
    """Retrieves the last N messages from episodic memory in chronological order."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Get last N messages sorted descending, then reverse to get chronological order
    cursor.execute("""
        SELECT role, message FROM episodic_memory 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))

def save_fact(fact: str):
    """Saves a permanent fact into semantic memory."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO semantic_memory (fact) VALUES (?)", (fact,))
        conn.commit()
        return f"Successfully remembered: {fact}"
    except sqlite3.IntegrityError:
        return f"I already know this fact: {fact}"
    finally:
        conn.close()

def forget_fact(fact_id: int):
    """Deletes a fact by ID from semantic memory."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM semantic_memory WHERE id = ?", (fact_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        return f"Successfully forgot fact ID {fact_id}."
    return f"Fact ID {fact_id} not found."

def get_all_facts():
    """Retrieves all permanent facts from semantic memory."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fact FROM semantic_memory")
    rows = cursor.fetchall()
    conn.close()
    return rows
