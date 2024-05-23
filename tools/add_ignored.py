import os
dirs = ("problems", "preparing_problems", "data", "accounts", "submissions", "sessions", "secret", "tmp", "logs", "contests")
os.chdir(os.path.dirname(os.path.dirname(__file__)))
for name in dirs:
    os.makedirs(name, exist_ok=True)
with open("data/problem_count", "w") as f:
    f.write("1000")
with open("data/submission_count", "w") as f:
    f.write("0")
with open("data/contest_count", "w") as f:
    f.write("0")
with open("data/public_problems.json", "w") as f:
    f.write("{}")
