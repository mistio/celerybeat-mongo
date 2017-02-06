import datetime

from celery import Celery

import mongoengine as me

from celerybeatmongo.schedulers import MongoScheduler


app = Celery('tasks')

app.conf.update({
    'CELERY_MONGODB_SCHEDULER_DB': 'celerybeatmongo-tests',
    'CELERY_MONGODB_SCHEDULER_COLLECTION': 'schedules',
    'CELERY_MONGODB_SCHEDULER_URL': 'mongodb://mongo',
    'CELERY_RESULT_BACKEND': 'rpc',
    'BROKER_URL': 'amqp://guest@rabbitmq',
    'CELERYBEAT_MAX_LOOP_INTERVAL': 1,
})

me.connect(host=app.conf['CELERY_MONGODB_SCHEDULER_URL'], db='results')


class TestMongoScheduler(MongoScheduler):
    UPDATE_INTERVAL = datetime.timedelta(seconds=1)


class Result(me.Document):
    name = me.StringField(required=True)
    date = me.DateTimeField(default=datetime.datetime.now, required=True)

    def __str__(self):
        return 'Result %s: %s' % (self.name, self.date)


@app.task
def task(name):
    print("Running task %s" % name)
    Result(name=name).save()
