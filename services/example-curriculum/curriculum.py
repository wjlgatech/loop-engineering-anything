"""A tiny real learning-tool library — the codebase-lane target for `edu-curriculum`.

Dependency-free lessons + a self-check quiz, so CLI-Anything has a real codebase
to make agent-native.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Lesson:
    slug: str
    title: str
    body: str
    quiz: list[tuple[str, str]] = field(default_factory=list)  # (question, answer)


class Curriculum:
    def __init__(self) -> None:
        self._lessons: dict[str, Lesson] = {}

    def add(self, lesson: Lesson) -> None:
        self._lessons[lesson.slug] = lesson

    def lessons(self) -> list[Lesson]:
        return list(self._lessons.values())

    def get(self, slug: str) -> Lesson | None:
        return self._lessons.get(slug)

    def grade(self, slug: str, answers: list[str]) -> float:
        """Return the fraction of quiz answers that are correct (0.0–1.0)."""
        lesson = self._lessons.get(slug)
        if lesson is None or not lesson.quiz:
            return 0.0
        correct = sum(1 for (_, a), given in zip(lesson.quiz, answers) if a.strip().lower() == given.strip().lower())
        return correct / len(lesson.quiz)
