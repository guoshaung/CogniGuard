"""配置与样例加载；不参与权限判断或教学生成。"""
from pathlib import Path
import yaml

from protection.common.schemas import StudentProfile, TeacherResource
from protection.common.text_utils import read_jsonl


def load_inputs(config_path, profiles_path, questions_path, resources_path):
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    profiles = {p.student_id: p for p in map(StudentProfile.from_dict, read_jsonl(profiles_path))}
    return config, profiles, read_jsonl(questions_path), list(map(TeacherResource.from_dict, read_jsonl(resources_path)))
