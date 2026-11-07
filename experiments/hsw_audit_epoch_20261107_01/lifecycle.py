"""Minimal retained issuance register. Associations are not legal judgements.

Canonical signature bytes: UTF-8, sorted JSON keys, no whitespace, ensure_ascii=False,
integer simulated clocks only; domain separation is signed along with version1.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DOMAIN = 'HSW-AUDIT-EPOCH-01/issuance/v1'
FIELDS = {'issue_id','source_id','issuer_id','recipient_pseudonym','content_version',
          'key_epoch','parent_issue_id','method','key_id','public_sha256','issued_at','message_code'}

def canonical(record: dict) -> bytes:
    if set(record) != FIELDS:
        raise ValueError('Exact issuance schema required')
    if type(record['issued_at']) is not int or record['issued_at'] < 0:
        raise ValueError('Clock must be a nonnegative simulated integer')
    for k in FIELDS - {'issued_at','parent_issue_id'}:
        if not isinstance(record[k],str) or not record[k]:raise ValueError('Nonempty string required: '+k)
    if record['parent_issue_id'] is not None and not isinstance(record['parent_issue_id'],str):
        raise ValueError('Parent must be an issue ID or null')
    if len(record['public_sha256']) != 64 or any(c not in '0123456789abcdef' for c in record['public_sha256']):
        raise ValueError('Exact SHA256 required')
    return json.dumps({'domain':DOMAIN,'record':record},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

class Register:
    def __init__(self, path: Path, public_key: bytes):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.verifier=Ed25519PublicKey.from_public_bytes(public_key)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS epochs (id TEXT PRIMARY KEY, start INTEGER, end INTEGER,
            audit_until INTEGER, compromised INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS issues (id TEXT PRIMARY KEY, body TEXT, signature TEXT,
            sha TEXT NOT NULL, epoch TEXT, code TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS permissions (issue TEXT, at INTEGER, status TEXT,
            PRIMARY KEY(issue,at));
        ''')
    def add_epoch(self, epoch: str, start: int, end: int, audit_until: int):
        if not 0<=start<end<=audit_until:raise ValueError('Invalid usage/retention interval')
        self.db.execute('INSERT INTO epochs(id,start,end,audit_until) VALUES(?,?,?,?)',(epoch,start,end,audit_until));self.db.commit()
    def register(self, record:dict, signature:bytes):
        b=canonical(record);self.verifier.verify(signature,b)
        ep=self.db.execute('SELECT start,end FROM epochs WHERE id=?',(record['key_epoch'],)).fetchone()
        if not ep or not ep[0]<=record['issued_at']<ep[1]:raise ValueError('Outside originator usage period')
        if record['parent_issue_id'] is not None and not self.db.execute('SELECT 1 FROM issues WHERE id=?',(record['parent_issue_id'],)).fetchone():
            raise ValueError('Unknown parent; no fabricated chain')
        self.db.execute('INSERT INTO issues VALUES(?,?,?,?,?,?)',(record['issue_id'],b.decode(),signature.hex(),record['public_sha256'],record['key_epoch'],record['message_code']))
        self.db.execute('INSERT INTO permissions VALUES(?,?,?)',(record['issue_id'],record['issued_at'],'ACTIVE'))
        self.db.commit()
    def permission(self, issue:str, at:int, status:str):
        if status not in {'ACTIVE','REVOKED','EXPIRED','DELEGATED'}:raise ValueError('Unknown permission status')
        if not self.db.execute('SELECT 1 FROM issues WHERE id=?',(issue,)).fetchone():raise ValueError('Unknown issue')
        self.db.execute('INSERT INTO permissions VALUES(?,?,?)',(issue,at,status));self.db.commit()
    def compromise(self, epoch:str):
        if self.db.execute('UPDATE epochs SET compromised=1 WHERE id=?',(epoch,)).rowcount!=1:raise ValueError('Unknown epoch')
        self.db.commit()
    def audit_candidates(self, at:int):
        # Includes historical epochs. Never given the query's true epoch or recipient.
        rows=self.db.execute('SELECT i.body,i.signature,e.compromised FROM issues i JOIN epochs e ON i.epoch=e.id WHERE i.body IS NOT NULL AND ?<=e.audit_until',(at,)).fetchall()
        out=[]
        for body,sig,compromised in rows:
            obj=json.loads(body);r=obj['record'];self.verifier.verify(bytes.fromhex(sig),canonical(r))
            out.append({**r,'evidence_status':'KEY_COMPROMISED' if compromised else 'REGISTERED_SIGNATURE_VALID'})
        return out
    def associate_ids(self, accepted_ids:list[str], at:int):
        unique=sorted(set(accepted_ids));candidates={r['issue_id']:r for r in self.audit_candidates(at)}
        if any(k not in candidates for k in unique):return {'status':'UNKNOWN_ISSUE','accepted':[]}
        if not unique:return {'status':'REJECT','accepted':[]}
        if len(unique)>1:return {'status':'AMBIGUOUS','accepted':unique}
        r=candidates[unique[0]]
        st=self.db.execute('SELECT status FROM permissions WHERE issue=? AND at<=? ORDER BY at DESC LIMIT 1',(unique[0],at)).fetchone()
        return {'status':'ASSOCIATED','record':r,'authorization_status_as_of':st[0] if st else 'UNKNOWN','query_clock':at,
                'legal_copyright_or_leaker_proof':False}
    def exact_public(self, text:bytes, at:int):
        q=hashlib.sha256(text).hexdigest()
        matches=[r['issue_id'] for r in self.audit_candidates(at) if r['public_sha256']==q]
        return self.associate_ids(matches,at)
    def close(self):self.db.close()

