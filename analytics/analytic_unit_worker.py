import config
import detectors
import json
import logging
import sys
import traceback
import time


logger = logging.getLogger('WORKER')


class AnalyticUnitWorker(object):
    models_cache = {}

    # TODO: get task as an object built from json
    async def do_task(self, task):
        try:
            type = task['type']
            analytic_unit_id = task['analyticUnitId']
            if type == "PREDICT":
                last_prediction_time = task['lastPredictionTime']
                pattern = task['pattern']
                result = await self.do_predict(analytic_unit_id, last_prediction_time, pattern)
            elif type == "LEARN":
                segments = task['segments']
                pattern = task['pattern']
                result = await self.do_learn(analytic_unit_id, segments, pattern)
            else:
                result = {
                    'status': "FAILED",
                    'error': "unknown type " + str(type)
                }
        except Exception as e:
            #traceback.extract_stack()
            error_text = traceback.format_exc()
            logger.error("do_task Exception: '%s'" % error_text)
            # TODO: move result to a class which renders to json for messaging to analytics
            result = {
                'task': type,
                'status': "FAILED",
                'analyticUnitId': analytic_unit_id,
                'error': str(e)
            }
        return result

    async def do_learn(self, analytic_unit_id, segments, pattern):
        model = self.get_model(analytic_unit_id, pattern)
        model.synchronize_data()
        last_prediction_time = await model.learn(segments)
        # TODO: we should not do predict before labeling in all models, not just in drops
        
        if pattern == 'DROP' and len(segments) == 0:
            # TODO: move result to a class which renders to json for messaging to analytics
            result = {
                'status': 'SUCCESS',
                'analyticUnitId': analytic_unit_id,
                'segments': [],
                'lastPredictionTime': last_prediction_time
            }
        else:
            result = await self.do_predict(analytic_unit_id, last_prediction_time, pattern)

        result['task'] = 'LEARN'
        return result

    async def do_predict(self, analytic_unit_id, last_prediction_time, pattern):
        model = self.get_model(analytic_unit_id, pattern)
        model.synchronize_data()
        segments, last_prediction_time = await model.predict(last_prediction_time)
        return {
            'task': 'PREDICT',
            'status': 'SUCCESS',
            'analyticUnitId': analytic_unit_id,
            'segments': segments,
            'lastPredictionTime': last_prediction_time
        }

    def get_model(self, analytic_unit_id, pattern_type):
        if analytic_unit_id not in self.models_cache:
            if pattern_type == 'GENERAL':
                model = detectors.GeneralDetector(analytic_unit_id)
            else:
                model = detectors.PatternDetector(analytic_unit_id, pattern_type)
            self.models_cache[analytic_unit_id] = model
        return self.models_cache[analytic_unit_id]