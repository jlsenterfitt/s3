"""Code to automatically select subreddits."""
import math
import datetime

import Connection
import FileConnection
import MiscObjects

def main():
  # Open credential file.
  credentialFileConnection = FileConnection.CredentialFileConnection()
  credentials = credentialFileConnection.Read()

  for credential in credentials:
    username = credential['username']

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
            sub_dict[sub_key].multi_display_name = multi.display_name

    # Get popular subs, push data to sub map
    popular_subs = connection.GetPopular()
    num_added = 0
    for sub in popular_subs:
      if num_added >= 5: break
      if sub.nsfw != connection.nsfw: continue

      if sub.fullname not in sub_dict:
        num_added += 1
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
    for sub_key in sub_dict:
      sub = sub_dict[sub_key]

      count += 1
      if count % 10 == 0:
        print 'Getting missing data for %s (%d of %d)' % (sub.display_name, count, len(sub_dict))
      connection.GetSubData(sub)

      # Calculate score
      n = math.ceil(sub.upvotes + sub.downvotes)
      if n:
        p = math.ceil(sub.upvotes) / n
        z = 1.65
        z2 = z * z

        start = p + z2 / (2 * n)
        mod = z * math.sqrt((1.0 / n) * p * (1 - p) + z2 / (4 * n * n))
        div = (1 + z2 * (1.0 / n))

        sub.vote_score_hi = (start + mod) / div
        sub.vote_score_lo = (start - mod) / div

        sub.score_hi = (sub.vote_score_hi**2 - 0.25) * math.sqrt(sub.posts_per_day)
        sub.score_lo = (sub.vote_score_lo**2 - 0.25) * math.sqrt(sub.posts_per_day)
      else:
        sub.vote_score_hi = -1.0
        sub.vote_score_lo = -1.0
        sub.score_hi = -1.0
        sub.score_lo = -1.0

    # Sort sub's by lo-score.
    lo_subs = sorted(sub_dict.values(), key=lambda a: a.score_lo, reverse=True)

    # Select subreddits, push to subscribed multi
    num_pushed = 0
    lowest_score = 1
    for sub in lo_subs:
      if sub.multi_display_name: continue
      if num_pushed >= 45: break
      if sub.nsfw != connection.nsfw: continue
      num_pushed += 1
      multi_dict['subscribed'].new_dict[sub.display_name] = sub
      lowest_score = sub.score_lo

    # Sort sub's by hi-score.
    hi_subs = sorted(sub_dict.values(), key=lambda a: a.score_hi, reverse=True)

    # Select subreddits, push to subscribed multi
    num_pushed = 0
    for sub in hi_subs:
      if sub.multi_display_name: continue
      if sub.display_name in multi_dict['subscribed'].new_dict: continue
      if num_pushed >= 5: break
      if sub.score_hi < lowest_score: break
      if sub.nsfw != connection.nsfw: continue
      num_pushed += 1
      multi_dict['subscribed'].new_dict[sub.display_name] = sub

    # Sort sub's by ppd.
    ppd_subs = sorted(sub_dict.values(), key=lambda a: a.posts_per_day, reverse=True)

    # Select subreddits, push to subscribed multi
    for sub in ppd_subs:
      if sub.nsfw != connection.nsfw: continue
      if sub.score_hi != -1: continue
      if len(multi_dict['subscribed'].new_dict) >= 50: break
      multi_dict['subscribed'].new_dict[sub.display_name] = sub

    # Remove outdated subs and add new subs.
    connection.UpdateSubscribed(multi_dict['subscribed'], sub_dict)

    # Export sub file.
    print 'Writing %d subs' % len(sub_dict)
    subFileConnection.Write(sub_dict)

    # Export vote file.
    print 'Writing %d votes' % len(vote_dict)
    voteFileConnection.Write(vote_dict)

    for sub in lo_subs:
      print '%s: %s %.2f %.2f %.2f %.2f %.2f' % (
          sub.display_name, sub.nsfw, sub.score_lo, sub.score_hi,
          sub.posts_per_day, sub.vote_score_lo, sub.vote_score_hi)

  print datetime.datetime.now()


if __name__ == '__main__':
  print datetime.datetime.now()
  main()
