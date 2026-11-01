from orchestration.task_names import task_name


def test_task_titles_describe_work_and_are_bounded():
    assert task_name('Task\nBuild the mobile voice interface\nContext\nDetails') == 'Build the mobile voice interface'
    assert task_name('Goal: Fix microphone reconnects') == 'Fix microphone reconnects'
    assert len(task_name('Review ' * 100)) <= 72
    assert task_name('') == 'Untitled task'
