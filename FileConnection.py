import json
import os


class _FileConnection(object):

  def __init__(self, username):
    self.directory_name = 'data/%s/' % username
    self.file_name = ''

  def _EnsureExistence(self):
    file_path = self.directory_name + self.file_name

    # Create directory if if doesn't exist.
    if not os.path.exists(self.directory_name):
      os.makedirs(self.directory_name)

    # Create file if it doesn't exist.
    if not os.path.exists(file_path):
      with open(file_path, 'w') as f:
        f.write('[]')

  def Read(self):
    self._EnsureExistence()
    file_path = self.directory_name + self.file_name

    with open(file_path, 'r') as f:
      contents = json.load(f)

      return contents

class CredentialFileConnection(_FileConnection):

  def __init__(self):
    self.directory_name = 'data/'
    self.file_name = 'subreddit_credentials.json'


class SubFileConnection(_FileConnection):

  def __init__(self, username):
    super(SubFileConnection, self).__init__(username)
    self.file_name = 'sub_data.json'

  def Write(self, raw_data):
    self._EnsureExistence()
    file_path = self.directory_name + self.file_name

    data = {}
    for key in raw_data:
      data[key] = raw_data[key].__dict__

    with open(file_path, 'w') as f:
      data_json = json.dumps(data, indent=2,sort_keys=True)
      f.write(data_json)


class VoteFileConnection(_FileConnection):

  def __init__(self, username):
    super(VoteFileConnection, self).__init__(username)
    self.file_name = 'vote_data.json'

  def Write(self, raw_data):
    self._EnsureExistence()
    file_path = self.directory_name + self.file_name

    sorted_votes = sorted(raw_data.values(), key=lambda a: a.created, reverse=True)

    """
    # Delete all but most recent 250 votes per sub.
    vote_count = {}
    deleted = 0
    for vote in sorted_votes:
      if vote.sr_fullname not in vote_count:
        vote_count[vote.sr_fullname] = 0
      if vote_count[vote.sr_fullname] < 250:
        vote_count[vote.sr_fullname] += 1
      else:
        del raw_data[vote.fullname]
        deleted += 1

    sorted_votes = sorted(raw_data.values(), key=lambda a: a.created, reverse=True)

    # Delete all but most recent 25000 votes overall.
    total = 0
    for vote in sorted_votes:
      if total < 25000:
        total += 1
      else:
        del raw_data[vote.fullname]
        deleted += 1

    print 'Deleted %d votes' % deleted
    """

    data = {}
    for key in raw_data:
      data[key] = raw_data[key].__dict__

    with open(file_path, 'w') as f:
      data_json = json.dumps(data, indent=True,sort_keys=True)
      f.write(data_json)
