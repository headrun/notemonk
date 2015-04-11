'''
User points, badges and awards system.
'''

from django.contrib.auth.models import User
from models import *

LEVEL_POINTS_PERCENT = .05

RATING_MULTIPLIER = {
                        Book:               4,
                        Note:               2,
                        AssociatedMedia:    2,
                        Answer:             2,
                        Question:           1,
                        UserProfile:        1,
                    }

def get_obj(klass, id):
    return klass.objects.get(pk=id)

class PointsSystem:
    @staticmethod
    def answer_add(code, data, user, answer):
        pass

    @staticmethod
    def video_add(code, data, user, avideo):
        pass

    @staticmethod
    def note_add(code, data, user, note):
        pass

    @staticmethod
    def question_add(code, data, user, question):
        pass

    @staticmethod
    def rated(code, data, target, num_ratings):

        level = Rateable.LEVELS.index(num_ratings) + 1

        if isinstance(target, ProfilePost):
            # no points for rating profile posts
            return

        ratings = target.ratings.order_by('date_added')[:num_ratings]
        value = sum(r.rating for r in ratings)

        if not value:
            return

        norm_value = value / value
        value = norm_value if value > 0 else -norm_value

        for index, r in enumerate(ratings):
            user_rating_level = PointsSystem._get_rating_level(index)
            level_diff = (level - user_rating_level) + 1

            rating_multiplier = 1
            if index == 0 and target.__class__ != UserProfile:
                # multiplier only for owner of item
                rating_multiplier = RATING_MULTIPLIER.get(target.__class__, 1)

            points = 1 if r.rating == value else -1
            points = points * level_diff * rating_multiplier

            userp = r.user.get_profile()
            userp.give_points(points)
            userp.save()

            data = {'target_type': target.ctype.id,
                    'target': target.id,
                    'num_ratings': num_ratings,
                    'position': index,
                    'rated_at_level': user_rating_level,
                    'current_level': level,
                    'level_diff': level_diff,
                    'rating_multiplier': rating_multiplier}
        
            p = PointsHistory.objects.create(user=r.user, points=points,
                code=code, data=repr(data))
            
            Activity.add(r.user, p)

    @staticmethod
    def _get_rating_level(count):
        for index, level_start in enumerate(Rateable.LEVELS):
            if count < level_start:
                return index + 1

        return len(Rateable.LEVELS) + 1

    @staticmethod
    def user_level_changed(code, data, user, prev_level, level):
        user = get_obj(User, user)
        
        if level > prev_level:
            level_score = UserProfile.LEVELS[level]
            sign = +1

        else:
            level_score = UserProfile.LEVELS[prev_level]
            sign = -1
        
        points = level_score * LEVEL_POINTS_PERCENT
        points = int(points) or 1
        points = sign * points

        referrer  = user.get_profile().referrer
        if not referrer:
            return

        referrer = referrer.get_profile()
        referrer.give_points(points)
        referrer.save()

        p = PointsHistory.objects.create(user=referrer.user, points=points,
            code=code, data=data)

        Activity.add(referrer.user, p)

    @staticmethod
    def dummy(code, data, **kwargs):
        return

def give_points(code, **kwargs):
    points_fn = getattr(PointsSystem, code, PointsSystem.dummy)
    points_fn(code, repr(kwargs), **kwargs)
