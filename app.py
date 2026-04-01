from flask import Flask, render_template, request, redirect, session
import os
import PyPDF2
import requests
import json
import sqlite3

# ==========================
# 🔐 PUT YOUR REAL API KEY HERE
# ==========================
API_KEY = "AIzaSyCA-rAmYexLOxSnGvK4xh6io9UKiiR-FEU"

app = Flask(__name__)
app.secret_key = "quizgame"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ==========================
# 🗄 DATABASE
# ==========================
def init_db():
    conn = sqlite3.connect("game.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        total_stars INTEGER DEFAULT 0,
        total_gems INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ==========================
# 📄 Extract text from PDF
# ==========================
def extract_text(filepath):
    text = ""
    with open(filepath, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content
    return text


# ==========================
# 🤖 Generate Questions
# ==========================
def generate_questions(text):

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    prompt = f"""
    Create 10 multiple choice questions for school children.

    Return ONLY valid JSON.
    Do not include markdown or explanation.

    Format:

    [
      {{
        "question": "Question text",
        "options": ["A", "B", "C", "D"],
        "answer": "Correct option text"
      }}
    ]

    Text:
    {text[:2000]}
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)

    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    if response.status_code != 200:
        return []

    try:
        result = response.json()
        output_text = result["candidates"][0]["content"]["parts"][0]["text"]
        questions = json.loads(output_text)
        return questions
    except Exception as e:
        print("JSON ERROR:", e)
        return []
# ==========================
# 🏠 Home
# ==========================
@app.route("/")
def index():
    return render_template("index.html")


# ==========================
# 📤 Upload PDF
# ==========================
@app.route("/upload", methods=["POST"])
def upload():

    username = request.form["username"]
    session["username"] = username

    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (username) VALUES (?)", (username,))
    conn.commit()
    conn.close()

    if not os.path.exists("uploads"):
        os.makedirs("uploads")

    file = request.files["pdf"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    text = extract_text(filepath)
    questions = generate_questions(text)

    if not questions:
        return "No questions generated."

    session["questions"] = questions
    session["current_question"] = 0
    session["score"] = 0
    session["review"] = []

    return redirect("/quiz")


# ==========================
# 🧠 Quiz
# ==========================
@app.route("/quiz", methods=["GET", "POST"])
def quiz():

    questions = session.get("questions", [])
    current = session.get("current_question", 0)
    score = session.get("score", 0)
    review = session.get("review", [])

    if not questions:
        return "No questions generated."

    if request.method == "POST":
        selected = request.form.get("option")
        correct = questions[current]["answer"]

        review.append({
            "question": questions[current]["question"],
            "selected": selected,
            "correct": correct
        })

        if selected == correct:
            score += 1

        session["score"] = score
        session["review"] = review
        session["current_question"] = current + 1
        current += 1

    if current >= len(questions):
        return redirect("/result")

    progress = int((current / len(questions)) * 100)

    return render_template(
        "quiz.html",
        question=questions[current],
        qno=current + 1,
        total=len(questions),
        progress=progress
    )


# ==========================
# 🏆 Result
# ==========================
@app.route("/result")
def result():

    score = session.get("score", 0)
    questions = session.get("questions", [])
    review = session.get("review", [])

    total = len(questions)
    stars = score
    gems = stars // 5   # LOW GEM SYSTEM

    username = session.get("username")

    conn = sqlite3.connect("game.db")
    c = conn.cursor()

    c.execute("""
        UPDATE players
        SET total_stars = total_stars + ?,
            total_gems = total_gems + ?
        WHERE username = ?
    """, (stars, gems, username))

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        score=score,
        total=total,
        stars=stars,
        gems=gems,
        review=review
    )


# ==========================
# 🏆 Leaderboard
# ==========================
@app.route("/leaderboard")
def leaderboard():

    conn = sqlite3.connect("game.db")
    c = conn.cursor()

    c.execute("""
    SELECT username, total_stars, total_gems
    FROM players
    ORDER BY total_gems DESC, total_stars DESC
""")

    players = c.fetchall()
    conn.close()

    return render_template("leaderboard.html", players=players)


# ==========================
# ▶ Run
# ==========================
if __name__ == "__main__":
    app.run(debug=True)