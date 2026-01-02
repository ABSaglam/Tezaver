
import json
from pathlib import Path
from datetime import datetime
from tezaver.core import coin_cell_paths

AGENDA_PATH = coin_cell_paths.get_library_root() / "user_agenda.json"

def load_agenda():
    try:
        if not AGENDA_PATH.exists():
            return {"date": datetime.now().strftime("%Y-%m-%d"), "tasks": []}
        
        with open(AGENDA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Reset if new day? Optional. Let's keep tasks until cleared for now, 
        # or maybe reset "done" status? 
        # User request "Bugün yapacaklarım" implies daily.
        # Let's simple load for now.
        return data
    except:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "tasks": []}

def save_agenda(data):
    try:
        with open(AGENDA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def add_coltask(text):
    data = load_agenda()
    data['tasks'].append({"text": text, "done": False, "created_at": datetime.now().isoformat()})
    save_agenda(data)
    
def toggle_task(idx, done):
    data = load_agenda()
    if 0 <= idx < len(data['tasks']):
        data['tasks'][idx]['done'] = done
        save_agenda(data)

def delete_task(idx):
    data = load_agenda()
    if 0 <= idx < len(data['tasks']):
        data['tasks'].pop(idx)
        save_agenda(data)
