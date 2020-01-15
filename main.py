"""Code to automatically select subreddits."""
import datetime
import math
import os
import random

import Connection
import FileConnection
import MiscObjects

NUM_SUBS = 50

def main():
  # Update where we're working from.
  # os.chdir("C:\Users\Justin\Google Drive\Notes\s3")

  # Open credential file.
  credentialFileConnection = FileConnection.CredentialFileConnection()
  credentials = credentialFileConnection.Read()

  for credential in credentials:
    username = credential['username']

    NUM_SUBS = credential['size']

    connection = Connection.Connection(
        credential['client_id'],
        credential['client_secret'],
        username,
        credential['password'],
        credential['nsfw'])

    # Create sub file connection.
    subFileConnection = FileConnection.SubFileConnection(username)

    # Create vote file connection.
    voteFileConnection = FileConnection.VoteFileConnection(username)

    # Create global maps.
    multi_dict = {}
    sub_dict = MiscObjects.SubredditMap()
    vote_dict = {}

    # Merge in historical sub data.
    sub_data = subFileConnection.Read()
    print 'Read %d subs from file' % len(sub_data)
    for key in sub_data:
      sub_dict.Add(key, sub_data[key])

    # Read vote file, push data to sub and vote maps
    votes = voteFileConnection.Read()
    print 'Read %d votes from file' % len(votes)
    for key in votes:
      vote = votes[key]

      if vote['sr_fullname'] not in sub_dict:
        new_sub = MiscObjects.Subreddit()
        new_sub.fullname = vote['sr_fullname']
        new_sub.display_name = vote['sr_display_name']
        sub_dict.Merge(vote['sr_fullname'], new_sub)

      new_vote = MiscObjects.Vote()

      new_vote.created = vote['created']
      new_vote.fullname = vote['fullname']
      new_vote.sr_fullname = vote['sr_fullname']
      new_vote.sr_display_name = vote['sr_display_name']
      new_vote.type = vote['type']

      vote_dict[new_vote.fullname] = new_vote

    # Get votes via API, push data to sub and vote maps
    votes = connection.GetVotes()
    for vote in votes:
      if vote.sr_fullname not in sub_dict:
        new_sub = MiscObjects.Subreddit()
        new_sub.fullname = vote.sr_fullname
        new_sub.display_name = vote.sr_display_name
        sub_dict.Merge(vote.sr_fullname, new_sub)

      vote_dict[vote.fullname] = vote

    # Get subscribed subs via API, push data to sub and multi map
    current_subs = connection.GetSubscribed()
    new_multi = MiscObjects.Multi()
    new_multi.display_name = 'subscribed'
    for sub in current_subs:
      new_multi.current_list.append(sub)

      sub_dict.Merge(sub.fullname, sub)
    multi_dict['subscribed'] = new_multi

    # Get multi's via API, push data to sub map and multi map
    multis = connection.GetMultis()
    for multi in multis:
      multi_dict[multi.display_name] = multi

      for sub_name in multi.current_list:
        for sub_key in sub_dict:
          if sub_dict[sub_key].display_name == sub_name:
            sub_dict[sub_key].multi_display_name.append(multi.display_name)

    # Get popular subs, push data to sub map
    popular_subs = connection.GetPopular()
    for sub in popular_subs:
      if sub.nsfw != connection.nsfw: continue

      if sub.fullname not in sub_dict:
        sub_dict[sub.fullname] = sub

    # Add vote data to subs.
    sorted_votes = sorted(vote_dict.values(), key=lambda a: a.created, reverse=True)
    mod = 1 - (1.0 / len(sorted_votes))
    current_mod = 1.0
    for vote in sorted_votes:
      if vote.type == 'upvoted':
        sub_dict[vote.sr_fullname].upvotes += current_mod
      elif vote.type == 'downvoted':
        sub_dict[vote.sr_fullname].downvotes += current_mod
      current_mod *= mod

    # Finalize data for all subs.
    count = 0
    for sub_key in sorted(
        sub_dict, key = lambda sub_key: sub_dict[sub_key].last_updated):
      sub = sub_dict[sub_key]

      count += 1
      # 10 chosen to ensure slow update of cache.
      if count <= 10 or not sub.last_updated:
        print 'Getting missing data for %s (%d of %d)' % (sub.display_name, count, len(sub_dict))
        connection.GetSubData(sub)

      # Calculate score
      n = math.ceil(sub.upvotes + sub.downvotes)
      if sub.posts_per_day > 0: ppd_mod = math.log10(sub.posts_per_day)
      else: ppd_mod = 0

      if n:
        p = math.ceil(sub.upvotes) / n
        z = 2.576 # 99% CI
        z2 = z * z

        # Wilson score interval.
        start = p + z2 / (2 * n)
        mod = z * math.sqrt((1.0 / n) * p * (1 - p) + z2 / (4 * n * n))
        div = (1 + z2 * (1.0 / n))

        sub.vote_score_hi = (start + mod) / div
        sub.vote_score_lo = (start - mod) / div

        # Ensure subs w/ < 50% don't get positive scores.
        # Hi-volume bad subs could overwhelm low-volume good ones otherwise.
        sub.score_hi = sub.vote_score_hi**2 * ppd_mod
        sub.score_lo = sub.vote_score_lo**2 * ppd_mod
        sub.score_random = random.triangular(sub.score_lo, sub.score_hi)

        # New odds-based version of scoring.
        if sub.vote_score_hi < 1.0:
          sub.score_hi = (sub.vote_score_hi / (1 - sub.vote_score_hi)) * ppd_mod
        else:
          sub.score_hi = 100.0 * ppd_mod

      else:
        # 0.82 is wilson score(1 success, 2 trials) squared.
        sub.vote_score_hi = 1.0 * ppd_mod
        sub.vote_score_lo = 1.0 * ppd_mod
        sub.score_hi = 100.0 * ppd_mod
        sub.score_lo = 1.0 * ppd_mod
        sub.score_random = 1.0 * ppd_mod

    # Sort sub's.
    hi_subs = sorted(sub_dict.values(), key=lambda a: a.score_hi, reverse=True)

    # Select subreddits on score, push to subscribed multi
    for sub in hi_subs:
      if 'remove' in sub.multi_display_name: continue
      if sub.display_name in multi_dict['subscribed'].new_dict: continue
      if len(multi_dict['subscribed'].new_dict) >= NUM_SUBS: break
      if sub.nsfw != connection.nsfw: continue
      multi_dict['subscribed'].new_dict[sub.display_name] = sub

    # Sort sub's by ppd.
    ppd_subs = sorted(sub_dict.values(), key=lambda a: a.posts_per_day, reverse=True)

    # Select subreddits on post per day, push to subscribed multi
    for sub in ppd_subs:
      if sub.nsfw != connection.nsfw: continue
      if sub.score_hi != -1: continue
      if len(multi_dict['subscribed'].new_dict) >= NUM_SUBS: break
      multi_dict['subscribed'].new_dict[sub.display_name] = sub

    # Remove outdated subs and add new subs.
    connection.UpdateSubscribed(multi_dict['subscribed'], sub_dict)

    """
    # Sort sub's by vote_score_hi.
    vote_hi_subs = sorted(sub_dict.values(), key=lambda a: a.vote_score_hi, reverse=True)

    # Fill vote_hi multi
    print 'starting vote_hi'
    for sub in vote_hi_subs:
      if 'remove' in sub.multi_display_name: continue
      if len(multi_dict['vote_hi'].new_dict) >= NUM_SUBS: break
      if sub.nsfw != connection.nsfw: continue
      if sub.posts_per_day < 1.0 / 7.0: continue
      multi_dict['vote_hi'].new_dict[sub.display_name] = sub

    # Remove outdated subs and add new subs.
    connection.UpdateMulti(multi_dict['vote_hi'], sub_dict)
    print 'ending vote_hi'
    """

    # Export sub file.
    print 'Writing %d subs' % len(sub_dict)
    subFileConnection.Write(sub_dict)

    # Export vote file.
    print 'Writing %d votes' % len(vote_dict)
    voteFileConnection.Write(vote_dict)

    """
    for sub in hi_subs:
      print '%s: %s %.2f %.2f' % (
          sub.display_name, sub.nsfw, sub.posts_per_day, sub.vote_score_lo)
    """

  print datetime.datetime.now()


if __name__ == '__main__':
  print datetime.datetime.now()
  main()

