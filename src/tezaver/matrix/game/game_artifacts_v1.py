import json
import os
from pathlib import Path
from dataclasses import asdict, is_dataclass
import logging

from tezaver.matrix.game.game_models_v1 import GameSummary, GameStep, GameTrade

logger = logging.getLogger(__name__)

class GameArtifactsWriter:
    def __init__(self, runs_dir: str, game_run_id: str):
        self.run_dir = Path(runs_dir) / game_run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.game_run_id = game_run_id
        
    def write_manifest(self, manifest_data: dict):
        path = self.run_dir / "game_manifest.json"
        with open(path, "w") as f:
            json.dump(manifest_data, f, indent=2)
            
    def write_summary(self, summary: GameSummary):
        path = self.run_dir / "game_summary.json"
        with open(path, "w") as f:
            if is_dataclass(summary):
                json.dump(asdict(summary), f, indent=2)
            else:
                json.dump(summary, f, indent=2)
                
    def write_steps(self, steps: list[GameStep]):
        path = self.run_dir / "game_steps.ndjson"
        with open(path, "w") as f:
            for step in steps:
                if is_dataclass(step):
                    f.write(json.dumps(asdict(step)) + "\n")
                else:
                    f.write(json.dumps(step) + "\n")
                    
    def write_trades(self, trades: list[GameTrade]):
        path = self.run_dir / "game_trades.json"
        with open(path, "w") as f:
            data = [asdict(t) if is_dataclass(t) else t for t in trades]
            json.dump(data, f, indent=2)
            
    def write_chart_marks(self, marks: list[dict]):
        path = self.run_dir / "game_chart_marks.json"
        with open(path, "w") as f:
            json.dump(marks, f, indent=2)
            
    def get_run_dir(self) -> Path:
        return self.run_dir
