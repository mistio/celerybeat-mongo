# Copyright 2018 Regents of the University of Michigan

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0

import datetime
import mongoengine as me
from celery import current_app
import celery.schedules


def get_periodic_task_collection():
    return (
        getattr(current_app.conf, 'CELERY_MONGODB_SCHEDULER_COLLECTION', '') or
        'schedules'
    )


#: Authorized values for PeriodicTask.Interval.period
PERIODS = ('days', 'hours', 'minutes', 'seconds', 'microseconds')


class PeriodicTask(me.DynamicDocument):
    """mongo database model that represents a periodic task"""

    meta = {'collection': get_periodic_task_collection(),
            'allow_inheritance': True}

    class Interval(me.EmbeddedDocument):
        meta = {'allow_inheritance': True}

        every = me.IntField(min_value=0, default=0, required=True)
        period = me.StringField(choices=PERIODS)

        @property
        def schedule(self):
            return celery.schedules.schedule(
                datetime.timedelta(**{self.period: self.every}))

        @property
        def period_singular(self):
            return self.period[:-1]

        def __unicode__(self):
            if self.every == 1:
                return 'every {0.period_singular}'.format(self)
            return 'every {0.every} {0.period}'.format(self)

    class Crontab(me.EmbeddedDocument):
        meta = {'allow_inheritance': True}

        minute = me.StringField(default='*', required=True)
        hour = me.StringField(default='*', required=True)
        day_of_week = me.StringField(default='*', required=True)
        day_of_month = me.StringField(default='*', required=True)
        month_of_year = me.StringField(default='*', required=True)

        @property
        def schedule(self):
            return celery.schedules.crontab(
                minute=self.minute,
                hour=self.hour,
                day_of_week=self.day_of_week,
                day_of_month=self.day_of_month,
                month_of_year=self.month_of_year,
            )

        def __unicode__(self):

            def rfield(field):
                return field and str(field).replace(' ', '') or '*'

            return '{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
                rfield(self.minute), rfield(self.hour),
                rfield(self.day_of_week), rfield(self.day_of_month),
                rfield(self.month_of_year),
            )

    name = me.StringField(unique=True)
    task = me.StringField(required=True)

    interval = me.EmbeddedDocumentField(Interval)
    crontab = me.EmbeddedDocumentField(Crontab)

    args = me.ListField()
    kwargs = me.DictField()

    queue = me.StringField()
    exchange = me.StringField()
    routing_key = me.StringField()
    soft_time_limit = me.IntField()

    expires = me.DateTimeField()
    start_after = me.DateTimeField()
    enabled = me.BooleanField(default=False)

    last_run_at = me.DateTimeField()

    total_run_count = me.IntField(min_value=0, default=0)
    max_run_count = me.IntField(min_value=0, default=0)

    date_changed = me.DateTimeField()
    description = me.StringField()

    run_immediately = me.BooleanField()

    # objects = managers.PeriodicTaskManager()
    no_changes = False

    def clean(self):
        """validation by mongoengine to ensure that you only have
        an interval or crontab schedule, but not both simultaneously"""
        if self.interval and self.crontab:
            msg = 'Cannot define both interval and crontab schedule.'
            raise me.ValidationError(msg)
        if not (self.interval or self.crontab):
            msg = 'Must defined either interval or crontab schedule.'
            raise me.ValidationError(msg)

    @property
    def schedule(self):
        if self.interval:
            return self.interval.schedule
        elif self.crontab:
            return self.crontab.schedule
        else:
            raise Exception("must define interval or crontab schedule")

    def __unicode__(self):
        fmt = '{0.name}: {{no schedule}}'
        if self.interval:
            fmt = '{0.name}: {0.interval}'
        elif self.crontab:
            fmt = '{0.name}: {0.crontab}'
        else:
            raise Exception("must define interval or crontab schedule")
        return fmt.format(self)
