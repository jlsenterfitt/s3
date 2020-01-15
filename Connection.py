import requests
import time

import MiscObjects

_retry_delays = [0, 0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.3, 2.1, 3.4]

class Connection(object):

  def __init__(self, client_id, client_secret, username, password, nsfw):
    self.average_time = 0.9
    self.headers = None
    self.limit_left = None
    self.nsfw = nsfw
    self.time_left = None
    self.username = username

    client_auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    print 'Client authenticated...'

    post_data = {
        'grant_type': 'password',
        'username': username,
        'password': password}

    response_json = self._PostRequest(
        'https://www.reddit.com/api/v1/access_token',
        auth=client_auth,
        data=post_data)

    self.headers = {
        'Authorization': 'bearer ' + response_json['access_token'],
        'User-Agent': 'subreddit_picker:v0.0.1'}
    print 'OAuth received...'

  def _DeleteRequest(self, *args, **kwargs):
    return self._Request(requests.delete, *args, **kwargs)

  def _GetRequest(self, *args, **kwargs):
    return self._Request(requests.get, *args, **kwargs)

  def _PostRequest(self, *args, **kwargs):
    return self._Request(requests.post, *args, **kwargs)

  def _PutRequest(self, *args, **kwargs):
    return self._Request(requests.put, *args, **kwargs)

  def _Request(self, func, *args, **kwargs):
    for retry_delay in _retry_delays:
      time.sleep(retry_delay)

      try:
        response = self._ThrottleHandler(func, *args, **kwargs).json()
        break
      except:
        if retry_delay < _retry_delays[-1:]:
          continue
        else:
          raise

    return response

  def _ThrottleHandler(self, func, *args, **kwargs):
    if self.headers: headers = self.headers
    else: headers = {'User-Agent': 'subreddit_picker:v0.0.1'}

    if not self.time_left: time.sleep(1.0)
    elif self.limit_left < 5: time.slee(self.time_left)
    else:
      wait = (float(self.time_left) ** 2) / (max(self.limit_left - 5, 1) ** 2)
      wait = max(wait - self.average_time, 0)
      wait = min(wait, self.time_left + 1)

      time.sleep(wait)

    start = time.time()
    response = func(headers=headers, timeout=10.0, *args, **kwargs)
    finish = time.time()

    self.average_time = self.average_time * 0.99 + (finish - start) * 0.01

    response_headers = response.headers

    if 'x-ratelimit-remaining' in response_headers:
      self.limit_left = float(response_headers['x-ratelimit-remaining'])
      self.time_left = float(response_headers['x-ratelimit-reset'])

    return response

  def GetVotes(self):
    vote_list = []
    request = 'https://oauth.reddit.com/user/%s/%s?limit=100&after=%s'
    types = ['downvoted', 'upvoted']

    for type in types:
      after = 'start'

      while after:
        new_request = request % (self.username, type, after)
        response_json = self._GetRequest(new_request)
        after = response_json['data']['after']

        for child in response_json['data']['children']:
          new_vote = MiscObjects.Vote()

          new_vote.created = child['data']['created']
          new_vote.fullname = child['data']['name']
          new_vote.sr_fullname = child['data']['subreddit_id']
          new_vote.sr_display_name = child['data']['subreddit']
          new_vote.type = type

          vote_list.append(new_vote)

        print 'Received %s response (Total %d)' % (type, len(vote_list))

    return vote_list

  def GetSubscribed(self):
    sub_list = []
    request = 'https://oauth.reddit.com/subreddits/mine/subscriber?limit=100'
    response_json = self._GetRequest(request)

    for child in response_json['data']['children']:
      new_sub = MiscObjects.Subreddit()

      new_sub.display_name = child['data']['display_name']
      new_sub.fullname = child['data']['name']
      new_sub.nsfw = child['data']['over18']

      sub_list.append(new_sub)

    print 'Received current subscription response.'
    return sub_list

  def GetMultis(self):
    multi_list = []
    request = 'https://oauth.reddit.com/api/multi/mine'
    response_json = self._GetRequest(request)

    for child in response_json:
      new_multi = MiscObjects.Multi()

      new_multi.display_name = child['data']['name']
      new_multi.multipath = child['data']['path']
      for shallow_sub in child['data']['subreddits']:
        new_multi.current_list.append(shallow_sub['name'])

      multi_list.append(new_multi)

    print 'Received multi list response.'
    return multi_list

  def GetPopular(self):
    sub_list = []
    request = 'https://oauth.reddit.com/subreddits/popular?limit=100&after='
    after = 'start'

    while len(sub_list) < 1000 and after:
      new_request = request + after
      response_json = self._GetRequest(new_request)
      after = response_json['data']['after']

      for child in response_json['data']['children']:
        new_sub = MiscObjects.Subreddit()

        new_sub.display_name = child['data']['display_name']
        new_sub.fullname = child['data']['name']
        new_sub.nsfw = child['data']['over18']

        sub_list.append(new_sub)

      print 'Received popular sub response (Total %d)' % len(sub_list)

    return sub_list

  def GetSubData(self, sub):
    try:
      request = 'https://oauth.reddit.com/r/%s/new?limit=100' % sub.display_name
      response_json = self._GetRequest(request)

      min = time.time() * 2
      for child in response_json['data']['children']:
        if child['data']['created'] - (8 * 60 * 60) < min:
          min = child['data']['created'] - (8 * 60 * 60)
      average_seconds_between = (time.time() - min) / 100.0
      sub.posts_per_day = (3600 * 24) / average_seconds_between

      if sub.nsfw is None:
        request = 'https://oauth.reddit.com/r/%s/about' % sub.display_name
        response_json = self._GetRequest(request)
        sub.nsfw = response_json['data']['over18']

      sub.last_updated = time.time()
    except:
      sub.last_updated = time.time()

      if response_json == {u'message': u'Forbidden', u'error': 403}:
        sub.posts_per_day = 0
        sub.nsfw = False
      elif response_json == {u'message': u'Not Found', u'error': 404}:
        sub.posts_per_day = 0
        sub.nsfw = False
      elif response_json == {u'reason': u'banned', u'message': u'Not Found', u'error': 404}:
        sub.posts_per_day = 0
        sub.nsfw = False
      elif response_json == {u'reason': u'private', u'message': u'Forbidden', u'error': 403}:
        sub.posts_per_day = 0
        sub.nsfw = False
      else:
        sub.posts_per_day = 0
        sub.nsfw = False
        print sub.display_name
        print response_json

  def UpdateMulti (self, multi, sub_dict):
    for sub_old in multi.current_list:
      for sub_key in sub_dict:
        if sub_dict[sub_key].display_name == sub_old:
          sub = sub_dict[sub_key]
          break

      if sub.display_name not in multi.new_dict:
        request = 'https://oauth.reddit.com/api/multi/%s/r/%s' % (
          multi.multipath, sub.display_name.lower())
        print self._DeleteRequest(request)
        print 'Removed %s from %s' % (sub.display_name, multi.display_name)
      else:
        print 'Keeping %s from %s' % (sub.display_name, multi.display_name)
        del multi.new_dict[sub.display_name]

    for display_name in multi.new_dict:
      sub = multi.new_dict[display_name]
      model = "{'name': %s}" % sub.display_name.lower()
      request = 'https://oauth.reddit.com/api/multi/%s/r/%s?model=%s' % (
        multi.multipath, sub.display_name.lower(), model)
      print self._PutRequest(request, model=model)
      print 'Added %s to %s' % (sub.display_name, multi.display_name)

  def UpdateSubscribed(self, multi, sub_dict):
    change_list = []

    for sub_old in multi.current_list:
      sub = sub_dict[sub_old.fullname]

      if sub.display_name not in multi.new_dict:
        request = 'https://oauth.reddit.com/api/subscribe?sr=%s&action=%s' % (
          sub.fullname, 'unsub')
        self._PostRequest(request)
        change_list.append(['Removed %s' % sub.display_name, sub.posts_per_day, sub.vote_score_hi, sub.score_hi])
      else:
        change_list.append(['Keeping %s' % sub.display_name, sub.posts_per_day, sub.vote_score_hi, sub.score_hi])
        del multi.new_dict[sub.display_name]

    for display_name in multi.new_dict:
      sub = multi.new_dict[display_name]
      request = 'https://oauth.reddit.com/api/subscribe?sr=%s&action=%s' % (
          sub.fullname, 'sub')
      self._PostRequest(request)
      change_list.append(['Added %s' % sub.display_name, sub.posts_per_day, sub.vote_score_hi, sub.score_hi])

    change_list.sort(key=lambda a: a[3])
    for change in change_list:
      print '%.2f\t%.2f\t%.2f\t%s' % (change[2], change[1], change[3], change[0])
