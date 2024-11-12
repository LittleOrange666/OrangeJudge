import os

dirs = ("data", "data/problems", "data/preparing_problems", "data/submissions", "tmp", "data/logs", "data/contests")
os.chdir(os.path.dirname(os.path.dirname(__file__)))
for name in dirs:
    os.makedirs(name, exist_ok=True)
if not os.path.exists("config.yaml"):
    with open("config.yaml", "w") as f:
        pass
