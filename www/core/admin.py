from django.contrib import admin
from core.models import *

for model_klass in (Category, LeaderBoardData, Question, Answer,\
    FBUserProfile, UserProfile, PointsHistory, Note, Book,\
    Node, AssociatedMedia, Ratings, Follows, Video, Image, Tag, TagItem,
    RedeemableItem, RedemptionItem, Redemption, Attachment):
    
    admin.site.register(model_klass)
