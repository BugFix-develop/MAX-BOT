from dataclasses import dataclass


#Создание структуры пользователя 
@dataclass
class User:
    max_user_id: str
    role: str = "student"

#Создание базовой структуры для задачи 
@dataclass
class Task:
    template_id: str
    question_text: str
    reference_answer: 