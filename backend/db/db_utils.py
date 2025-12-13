import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env if present

def get_connection():
    """
    Returns a MySQL connection object.
    Make sure you have DB credentials in .env or edit defaults below.
    """
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),   # <- change or set in .env
            database=os.getenv("DB_NAME", "retail_ops")
        )
        return conn
    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")
        return None
