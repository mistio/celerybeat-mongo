import time
import uuid
import datetime

from celerybeatmongo.models import PeriodicTask

from app import task, Result


PeriodicTask.objects.delete()
Result.objects.delete()


def get_name(name):
    return '%s:%s:%s' % (name, datetime.datetime.now().isoformat(),
                         uuid.uuid4().hex)


def test_generic():
    name = get_name('test_generic')
    task = PeriodicTask(
        name=name,
        task='app.task',
        args=(name, ),
        kwargs={},
        enabled=True,
        interval=PeriodicTask.Interval(every=3, period='seconds'),
        run_immediately=True,
    )
    task.save()
    time.sleep(10)
    task.reload()
    task.interval = PeriodicTask.Interval(every=5, period='seconds')
    task.save()
    time.sleep(16)
    results = list(Result.objects(name=name))
    for result in results:
        print(result)
    assert len(results) == 7
    timedeltas = [
        int(round((results[i].date - results[i-1].date).total_seconds()))
        for i in range(1, 7)
    ]
    print(timedeltas)
    assert timedeltas == [3, 3, 3, 5, 5, 5]


def test_max_run_count():
    name = get_name('test_max_run_count')
    PeriodicTask(
        name=name,
        task='app.task',
        args=(name, ),
        kwargs={},
        enabled=True,
        interval=PeriodicTask.Interval(every=1, period='seconds'),
        max_run_count=3,
        run_immediately=True,
    ).save()
    time.sleep(10)
    results = list(Result.objects(name=name))
    for result in results:
        print(result)
    assert len(results) == 3
