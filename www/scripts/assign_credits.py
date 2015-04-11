#!/usr/bin/env python
import sys
from decimal import Decimal

from django.db.models import Sum, Q

from core.models import *
import notification.models as notification

IGNORE_USERS = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

def ignore_points():
    points = 0

    for u in IGNORE_USERS:
        points += u.get_profile().points

    return points

def main(credits, mock=True):

    credits_assigned = 0.0
    total_points = UserProfile.objects.all().aggregate(Sum('points'))
    total_points = total_points['points__sum']
    total_points -= ignore_points()

    for u in UserProfile.objects.all():
        
        if u.user in IGNORE_USERS:
            continue

        if u.points <= 1:
            continue

        user_credits = (u.points / float(total_points)) * credits
        if not mock:
            cur_credits = Decimal(str(user_credits))
            u.credits += cur_credits
            u.save()
            notification.send([u.user], 'credits_earned',
                {'user': u.user, 'credits': '%.2f' % cur_credits})

        print '%20s\t%.2f' % (u.user.username, user_credits)
        credits_assigned += user_credits

    print 'Credits assigned: %.2f' % credits_assigned
    print 'Credits Leftover: %.2f' % (credits - credits_assigned)

if __name__ == '__main__':
    main(int(sys.argv[1]))
