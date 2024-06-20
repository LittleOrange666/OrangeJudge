import os
import shutil

dirs = ("problems", "preparing_problems", "data", "submissions", "tmp", "logs", "contests")
os.chdir(os.path.dirname(os.path.dirname(__file__)))
for name in dirs:
    os.makedirs(name, exist_ok=True)
if not os.path.exists("config.yaml"):
    shutil.copy("tools/default_config.yaml", "config.yaml")
