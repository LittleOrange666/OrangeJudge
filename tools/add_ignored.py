import os

dirs = ("problems", "preparing_problems", "data", "submissions", "tmp", "logs", "contests")
os.chdir(os.path.dirname(os.path.dirname(__file__)))
for name in dirs:
    os.makedirs(name, exist_ok=True)
if not os.path.exists("config.yaml"):
    with open("config.yaml", "w") as f:
        pass
