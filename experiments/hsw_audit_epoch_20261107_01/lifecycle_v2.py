"""Prospective offline lifecycle guards; v1 and generation freeze remain intact.

Only fixes time/compromise validation. Same signature bytes, keys, watermark and
identity schema. Not a new watermark algorithm or a trusted timestamp service.
"""
from lifecycle import Register
class StrictRegister(Register):
 def audit_candidates(self,at):
  if type(at) is not int or at<0:raise ValueError('Nonnegative integer query clock required')
  return [r for r in super().audit_candidates(at) if r['issued_at']<=at]
 def register(self,record,signature):
  ep=self.db.execute('SELECT compromised FROM epochs WHERE id=?',(record['key_epoch'],)).fetchone()
  if ep and ep[0]:raise ValueError('Compromised epoch cannot issue new copies')
  return super().register(record,signature)
 def permission(self,issue,at,status):
  import json
  row=self.db.execute('SELECT body FROM issues WHERE id=?',(issue,)).fetchone()
  if not row:raise ValueError('Unknown issue')
  issued=json.loads(row[0])['record']['issued_at']
  if type(at) is not int or at<issued:raise ValueError('Permission event cannot predate issuance')
  return super().permission(issue,at,status)
