import re


CYRRILIC_TO_LATTIN = str.maketrans({
    "а": "a",
    "в": "b",
    "с": "c",
    "е": "e",
    "о": "o",
    "р": "p",
    "х": "x",
    "у": "y",
})


#Перевод строки в стандартизированную
def normalize_answer(raw_answer: str) -> str:

    if not raw_answer:
        return raw_answer
    
    text = raw_answer.lower().replace(" ", "")

    text = text.translate(CYRRILIC_TO_LATTIN)

    text = text.replace("**2", "^2").replace("²", "^2")
    text = text.replace("**3", "^3").replace("³", "^3")



    text = re.sub(r"(вквадрате|во2|вовторой|встепени2)", "^2", text)
    text = re.sub(r"(вкубе|в3|втретьей|встепени3)", "^3", text)

    text = text.replace("*", "")
    return text


#Проверка на корректность введенного ответа пользователем 
def check_answer(user_input: str, expected_answer: str) -> tuple[bool, str]:

    answer_of_user = normalize_answer(user_input)
    expected_answer = normalize_answer(expected_answer)

    if(expected_answer == answer_of_user):
        return(True, "Ответ верный!")
    else:
        return(False, f"Ответ неверный.Верный ответ: {expected_answer}")

