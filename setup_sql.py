import pyodbc
import sys
import struct

token = sys.argv[1]
token_bytes = token.encode("UTF-16-LE")
token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
conn_str = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=test-rahul-sql-server.database.windows.net;DATABASE=master;"
SQL_COPT_SS_ACCESS_TOKEN = 1256
conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
cursor = conn.cursor()
try:
    cursor.execute("CREATE LOGIN [databricks-sql-server] FROM EXTERNAL PROVIDER")
    print("Created login for service principal on master")
except Exception as e:
    print(f"Login may already exist: {e}")
try:
    cursor.execute("CREATE USER [databricks-sql-server] FROM EXTERNAL PROVIDER")
    print("Created user on master")
except Exception as e:
    print(f"User may already exist: {e}")
conn.commit()
conn.close()
