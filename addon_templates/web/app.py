"""Customize this challenge:
 - Change the company name / theme in LOGIN_PAGE
 - Tweak the SQL query if you want a different injection class
 - Swap the welcome message etc.
The flag is read from the CHALL_FLAG env var that CTF Manager sets at deploy time.
"""
import os
import sqlite3
from flask import Flask, request, render_template_string

DB = "/app/users.db"
FLAG = os.environ.get("CHALL_FLAG", "bluebox{missing}")

app = Flask(__name__)

LOGIN_PAGE = """
<!doctype html>
<title>Acme Corp Login</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 420px; margin: 4rem auto; }
  input { display:block; width:100%; padding:8px; margin:6px 0 14px; }
  .msg { padding:8px; border-radius:4px; }
  .ok  { background:#d1fae5; color:#065f46; }
  .err { background:#fee2e2; color:#991b1b; }
</style>
<h1>Acme Corp</h1>
<p>Members only. Sign in to continue.</p>
<form method=post>
  <label>Username <input name=username></label>
  <label>Password <input name=password type=password></label>
  <button type=submit>Sign in</button>
</form>
{% if message %}<p class="msg {{cls}}">{{message}}</p>{% endif %}
"""


def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
    cur.execute("DELETE FROM users")
    cur.execute("INSERT INTO users VALUES (?, ?)", ("admin", "hunter2-but-you-wont-guess-this"))
    con.commit()
    con.close()


@app.route("/", methods=["GET", "POST"])
def login():
    message = None
    cls = "err"
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # VULNERABLE on purpose — string concatenation:
        query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
        con = sqlite3.connect(DB)
        try:
            row = con.execute(query).fetchone()
        except sqlite3.Error as e:
            row = None
            message = f"SQL error: {e}"
        con.close()

        if row is not None and message is None:
            message = f"Welcome back. {FLAG}"
            cls = "ok"
        elif message is None:
            message = "Invalid credentials."
    return render_template_string(LOGIN_PAGE, message=message, cls=cls)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
