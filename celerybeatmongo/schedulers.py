# Copyright 2018 Regents of the University of Michigan

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0

import mongoengine
import traceback
import datetime

from mongoengine.errors import SaveConditionError

from celerybeatmongo.models import PeriodicTask
from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger
from celery import current_app


class MongoScheduleEntry(ScheduleEntry):

    def __init__(self, task):
        self._task = task

        self.app = current_app._get_current_object()
        self.name = self._task.name
        self.task = self._task.task

        self.schedule = self._task.schedule

        self.args = self._task.args
        self.kwargs = self._task.kwargs
        self.options = {
            'queue': self._task.queue,
            'exchange': self._task.exchange,
            'routing_key': self._task.routing_key,
            'expires': self._task.expires,
            'soft_time_limit': self._task.soft_time_limit
        }
        if self._task.total_run_count is None:
            self._task.total_run_count = 0
        self.total_run_count = self._task.total_run_count

        if not self._task.last_run_at:
            self._task.last_run_at = self._default_now()
        self.last_run_at = self._task.last_run_at

    def _default_now(self):
        return self.app.now()

    def next(self):
        self._task.last_run_at = self.app.now()
        self._task.total_run_count += 1
        self._task.run_immediately = False
        return self.__class__(self._task)

    __next__ = next

    def is_due(self):
        if not self._task.enabled:
            return False, 5.0   # 5 second delay for re-enable.
        if hasattr(self._task, 'start_after') and self._task.start_after:
            if datetime.datetime.now() < self._task.start_after.replace(tzinfo=None):
                return False, 5.0
        if hasattr(self._task, 'max_run_count') and self._task.max_run_count:
            if (self._task.total_run_count or 0) >= self._task.max_run_count:
                return False, 5.0
        if self._task.run_immediately:
            # figure out when the schedule would run next anyway
            _, n = self.schedule.is_due(self.last_run_at)
            return True, n
        return self.schedule.is_due(self.last_run_at)

    def __repr__(self):
        return ('<{0} ({1} {2}(*{3}, **{4}) {{5}})>'.format(
            self.__class__.__name__,
            self.name, self.task, self.args,
            self.kwargs, self.schedule,
        ))

    def reserve(self, entry):
        new_entry = Scheduler.reserve(self, entry)
        return new_entry

    def save(self):
        if self.total_run_count > self._task.total_run_count:
            self._task.total_run_count = self.total_run_count
        if (
                self.last_run_at and self._task.last_run_at and
                self.last_run_at.replace(tzinfo=None) > self._task.last_run_at.replace(tzinfo=None)
        ):
            self._task.last_run_at = self.last_run_at
        self._task.run_immediately = False
        try:
            self._task.save(save_condition={})
        except SaveConditionError:  # Sleep and retry
            from time import sleep
            from random import random
            sleep(random())
            self._task.save(save_condition={})
        except Exception:
            get_logger(__name__).error(traceback.format_exc())


class MongoScheduler(Scheduler):

    #: how often should we sync in schedule information
    #: from the backend mongo database
    UPDATE_INTERVAL = datetime.timedelta(seconds=5)

    Entry = MongoScheduleEntry

    Model = PeriodicTask

    def __init__(self, *args, **kwargs):
        db = (
            getattr(current_app.conf, 'CELERY_MONGODB_SCHEDULER_DB', '') or
            getattr(current_app.conf, 'mongodb_scheduler_db', '') or
            'celery'
        )
        mongo_url = (
            getattr(current_app.conf, 'CELERY_MONGODB_SCHEDULER_URL', '') or
            getattr(current_app.conf, 'mongodb_scheduler_url', '') or
            'mongodb://localhost:27017'
        )
        self._mongo = mongoengine.connect(db, host=mongo_url)
        get_logger(__name__).info(
            "backend scheduler using %s/%s:%s",
            mongo_url, db, self.Model._get_collection().name)

        self._schedule = {}
        self._last_updated = None
        Scheduler.__init__(self, *args, **kwargs)
        self.max_interval = (
            kwargs.get('max_interval') or
            getattr(self.app.conf, 'CELERYBEAT_MAX_LOOP_INTERVAL', 0) or
            getattr(self.app.conf, 'beat_max_loop_interval', 0) or
            5
        )

    def setup_schedule(self):
        pass

    def requires_update(self):
        """check whether we should pull an updated schedule
        from the backend database"""
        if not self._last_updated:
            return True
        next_update = self._last_updated + self.UPDATE_INTERVAL
        return next_update < datetime.datetime.now()

    def get_from_database(self):
        self.sync()
        d = {}
        for doc in self.Model.objects():
            d[doc.name] = self.Entry(doc)
        return d

    @property
    def schedule(self):
        if self.requires_update():
            self._schedule = self.get_from_database()
            self._last_updated = datetime.datetime.now()
        return self._schedule

    def sync(self):
        for entry in list(self._schedule.values()):
            entry.save()

    def tick(self, *args, **kwargs):
        adjust = self.adjust
        intervals = []
        for entry in list(self.schedule.values()):
            is_due, next_time_to_run = self.is_due(entry)
            intervals.append(adjust(next_time_to_run))
            if is_due:
                # self.reserve() calls next(). TODO: investigate if required.
                self.reserve(entry)
                self.apply_entry(entry, producer=self.producer)
        return min(intervals + [self.max_interval])
