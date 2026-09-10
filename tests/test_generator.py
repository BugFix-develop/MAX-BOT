import pytest
from engine.generator import TaskGenerator
from core.models import Task


@pytest.fixture
def generator():
    return TaskGenerator()


def test_generator_initialization(generator):
    assert len(generator.templates) == 30
    assert len(generator.templates_by_id) == 30


def test_generate_random_task(generator):
    task = generator.generate_task()
    assert isinstance(task, Task)
    assert 1 <= task.template_id <= 30
    assert len(task.question_text) > 0
    assert len(task.reference_answer) > 0


def test_generate_all_30_templates(generator):
    for template_id in range(1, 31):
        task = generator.generate_task(template_id)
        assert task.template_id == template_id
        assert len(task.question_text) > 0
        assert len(task.reference_answer) > 0


def test_invalid_template_id(generator):
    with pytest.raises(ValueError):
        generator.generate_task(999)


def test_get_unique_task_deduplication(generator):
    user_id = "student_test_1"
    solved_history = set()

    def mock_checker(uid: str, text: str) -> bool:
        return text in solved_history


    for _ in range(5):
        task = generator.get_unique_task(
            user_id=user_id,
            template_id=1,
            checker=mock_checker
        )
        assert task.question_text not in solved_history
        solved_history.add(task.question_text)


def test_get_unique_task_fallback(generator):
    user_id = "student_test_2"

    all_possible = {f"Раскройте скобки: (x - {a})(x + {a})" for a in range(2, 16)}

    def mock_all_solved(uid: str, text: str) -> bool:
        return text in all_possible


    task = generator.get_unique_task(
        user_id=user_id,
        template_id=1,
        max_attempts=5,
        checker=mock_all_solved
    )
    assert task is not None
    assert isinstance(task, Task)


def test_generate_lesson_cycle(generator):
    tasks = generator.generate_lesson_cycle()
    assert len(tasks) == 5
    for task in tasks:
        assert isinstance(task, Task)
        assert len(task.question_text) > 0
        assert len(task.reference_answer) > 0
    assert tasks[0].template_id in range(1, 8)
    assert tasks[1].template_id in range(1, 8)
    assert tasks[2].template_id in range(8, 21)
    assert tasks[3].template_id in range(8, 21)
    assert tasks[4].template_id in range(21, 31)


def test_generate_teacher_variant(generator):
    tasks = generator.generate_teacher_variant(count=15)
    assert len(tasks) == 15
    template_ids = [t.template_id for t in tasks]
    assert len(set(template_ids)) == 15
    for task in tasks:
        assert isinstance(task, Task)
        assert len(task.question_text) > 0
        assert len(task.reference_answer) > 0


