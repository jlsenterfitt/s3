class Multi(object):

  def __init__(self):
    self.display_name = None
    self.current_list = []
    self.multipath = None
    self.new_dict = {}

  def __str__(self):
    return str(self.__dict__)

class Subreddit(object):

  def __init__(self):
    """Created by GetVotes
      display_name
      fullname
    """
    self.display_name = None
    self.downvotes = 0
    self.fullname = None
    self.multi_display_name = []
    self.nsfw = None
    self.posts_per_day = None
    self.score_hi = None
    self.score_lo = None
    self.upvotes = 0
    self.vote_score_hi = None
    self.vote_score_lo = None
    self.last_updated = 0

  def __str__(self):
    return str(self.__dict__)

class SubredditMap(dict):

  def Add(self, key, sub_data):
    new_sub = Subreddit()
    
    for param in sub_data:
      new_sub.__dict__[param] = sub_data[param]

    self[key] = new_sub

  def Merge(self, key, new_sub):
    if key not in self:
      self[key] = new_sub
    else:
      current_sub = self[key]

      for param in new_sub.__dict__:
        if current_sub.__dict__[param]: continue
        current_sub.__dict__[param] = new_sub.__dict__[param]

  def __str__(self):
    string = '{'
    for key in self:
      string += key + ': ' + str(self[key]) + ','
    string = string[0:-1]
    string += '}'
    return string

class Vote(object):

  def __init__(self):
    self.created = None
    self.fullname = None
    self.sr_fullname = None
    self.sr_display_name = None
    self.type = None

  def __str__(self):
    return str(self.__dict__)

