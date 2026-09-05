from dataclasses import dataclass


#Создание структуры пользователя 
@dataclass
class User:
    max_user_id: str
    role: str = "student"

#Создание базовой структуры для задачи 
@dataclass
class Task:
    template_id: int
    question_text: str
    reference_answer: str

#Проверка на верность ответа, которую ввел пользователь
@dataclass
class TaskResult:
    student_answer: str
    is_right_answer: bool

#
@dataclass 
class LessonPlan:
    topic: str
    grade: int
    tasks_block: list[Task]
    markdown: str
    time: int = 45