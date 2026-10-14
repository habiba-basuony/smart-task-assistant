from app.services.llm_service import validate_intent_output


def valid_task():
    return {
        "intent": "create_task",
        "assignee_name": "خالد",
        "description": "يراجع عرض السعر",
        "scope": None,
    }


def test_valid_task_is_accepted():
    result = validate_intent_output(valid_task())

    assert result["intent"] == "create_task"
    assert result["assignee_name"] == "خالد"
    assert result["description"] == "يراجع عرض السعر"


def test_assignee_cannot_be_a_list():
    data = valid_task()
    data["assignee_name"] = ["خالد"]

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_description_cannot_be_an_object():
    data = valid_task()
    data["description"] = {"task": "يراجع عرض السعر"}

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_missing_required_field_is_rejected():
    data = valid_task()
    del data["description"]

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_invalid_intent_is_rejected():
    data = valid_task()
    data["intent"] = "delete_company"

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_invalid_scope_is_rejected():
    data = {
        "intent": "list_tasks",
        "assignee_name": None,
        "description": None,
        "scope": "everyone",
    }

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_person_scope_requires_employee_name():
    data = {
        "intent": "list_tasks",
        "assignee_name": None,
        "description": None,
        "scope": "person",
    }

    result = validate_intent_output(data)

    assert result["intent"] == "unknown"


def test_valid_policy_question_is_accepted():
    data = {
        "intent": "policy_question",
        "assignee_name": None,
        "description": None,
        "scope": None,
    }

    result = validate_intent_output(data)

    assert result["intent"] == "policy_question"


def test_non_dictionary_output_is_rejected():
    result = validate_intent_output(["create_task", "خالد"])

    assert result["intent"] == "unknown"