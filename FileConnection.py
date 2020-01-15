import bz2
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
    if not os.path.exists(file_path + '.bz2'):
      self._WriteToFile([])

  def _WriteToFile(self, data_dict):
    file_path = self.directory_name + self.file_name
    data_json = json.dumps(data_dict, indent=2, sort_keys=True)

    with bz2.BZ2File(file_path + '.bz2', 'wb') as f:
      f.write(data_json)
    

  def Read(self):
    file_path = self.directory_name + self.file_name

    self._EnsureExistence()

    try:
      with bz2.BZ2File(file_path + '.bz2', 'r') as f:
        raw_contents = f.read()
        contents = json.loads(raw_contents)
    except IOError:
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

    data = {}
    for key in raw_data:
      data[key] = raw_data[key].__dict__

    self._WriteToFile(data)


class VoteFileConnection(_FileConnection):

  def __init__(self, username):
    super(VoteFileConnection, self).__init__(username)
    self.file_name = 'vote_data.json'

  def Write(self, raw_data):
    self._EnsureExistence()

    sorted_votes = sorted(raw_data.values(), key=lambda a: a.created, reverse=True)

    # 256 votes is purely to keep storage size in check.
    max_votes = 256
    vote_count = {}
    sub_listing = set()
    deleted = 0
    for vote in sorted_votes:
      if vote.sr_fullname not in vote_count:
        vote_count[vote.sr_fullname] = 0

      if vote_count[vote.sr_fullname] < max_votes:
        vote_count[vote.sr_fullname] += 1
      else:
        del raw_data[vote.fullname]
        deleted += 1

    """
    # Delete all but most recent 25000 votes overall.
    total = 0
    for vote in sorted_votes:
      if total < 25000:
        total += 1
      else:
        del raw_data[vote.fullname]
        deleted += 1
    """
    print 'Deleted %d votes' % deleted

    data = {}
    for key in raw_data:
      data[key] = raw_data[key].__dict__

    self._WriteToFile(data)

