"""Private bench scheduler for one lab queue.

Seeing a single function is not enough to rebuild the ordering rule.
The protected target is the three function bodies together.
"""

SLOT_MINUTES = 25


class QueueWindow:
    """One named block of open bench time."""

    def __init__(self, label: str, capacity: int) -> None:
        self.label = label
        self.capacity = capacity


def parse_jobs(raw: str) -> list[dict]:
    """Read one job per line: name, urgency, size."""
    jobs = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        name, urgency, size = text.split(",")
        jobs.append(
            {
                "name": name.strip(),
                "urgency": int(urgency),
                "size": int(size),
                "minutes": int(size) * SLOT_MINUTES,
            }
        )
    return jobs


def score_job(job: dict, weight: float) -> float:
    """Rank a job by urgency minus a size penalty."""
    penalty = job["size"] * (1.0 - weight) * SLOT_MINUTES
    return float(job["urgency"]) * 10.0 - penalty


def assign_slots(
    jobs: list[dict], openings: list[str], weight: float
) -> list[tuple[str, str]]:
    """Fill openings with the highest scores, one job per slot."""
    ranked = sorted(jobs, key=lambda job: score_job(job, weight), reverse=True)
    placed = []
    for opening, job in zip(openings, ranked):
        placed.append((opening, f"{job['name']}@{job['minutes']}"))
    return placed
