"""UNIT_FIXTURE only: no artificial tokens counted as actual watermark samples."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from lifecycle import Register,canonical

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.key=Ed25519PrivateKey.generate()
        self.pub=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.reg=Register(Path(self.tmp.name)/'private_fixture.sqlite3',self.pub)
        self.reg.add_epoch('E1',0,100,900);self.reg.add_epoch('E2',100,200,1000)
    def tearDown(self):self.reg.close();self.tmp.cleanup()
    def row(self,id='I01',text=b'author text',epoch='E1',clock=20,recipient='B',parent=None):
        return {'issue_id':id,'source_id':'S01','issuer_id':'SIMULATED_ISSUER','recipient_pseudonym':recipient,
          'content_version':'v1','key_epoch':epoch,'parent_issue_id':parent,'method':'UNIT_FIXTURE',
          'key_id':epoch+'_TEST_ONLY','public_sha256':hashlib.sha256(text).hexdigest(),'issued_at':clock,'message_code':id}
    def add(self,**kw):
        r=self.row(**kw);self.reg.register(r,self.key.sign(canonical(r)));return r
    def test_canonical_order(self):
        r=self.row();self.assertEqual(canonical(r),canonical(dict(reversed(list(r.items())))))
    def test_signature_tampering(self):
        r=self.row();s=self.key.sign(canonical(r));r['recipient_pseudonym']='C'
        with self.assertRaises(InvalidSignature):self.reg.register(r,s)
    def test_duplicate_issue(self):
        r=self.add()
        with self.assertRaises(sqlite3.IntegrityError):self.reg.register(r,self.key.sign(canonical(r)))
    def test_duplicate_code(self):
        r=self.add();r['issue_id']='DIFFERENT'
        with self.assertRaises(sqlite3.IntegrityError):self.reg.register(r,self.key.sign(canonical(r)))
    def test_old_after_rotation(self):
        self.add();self.add(id='I02',text=b'new version',epoch='E2',clock=120)
        a=self.reg.exact_public(b'author text',150)
        self.assertEqual(a['record']['key_epoch'],'E1');self.assertEqual(a['record']['issue_id'],'I01')
    def test_revocation_not_identity(self):
        self.add();self.reg.permission('I01',130,'REVOKED')
        a=self.reg.exact_public(b'author text',150)
        self.assertEqual(a['record']['issue_id'],'I01');self.assertEqual(a['authorization_status_as_of'],'REVOKED')
    def test_forwarding_not_new_recipient(self):
        self.add(recipient='B');self.assertEqual(self.reg.exact_public(b'author text',150)['record']['recipient_pseudonym'],'B')
    def test_direct_reissue_parent_preserved(self):
        self.add();self.add(id='I02',text=b'C issued from author',recipient='C',epoch='E2',clock=120,parent='I01')
        self.assertEqual(self.reg.exact_public(b'author text',150)['record']['recipient_pseudonym'],'B')
        self.assertEqual(self.reg.exact_public(b'C issued from author',150)['record']['parent_issue_id'],'I01')
    def test_unknown_parent(self):
        with self.assertRaises(ValueError):self.add(parent='ABSENT')
    def test_old_key_no_new_issuance(self):
        with self.assertRaises(ValueError):self.add(clock=120)
    def test_all_epoch_scan(self):
        self.add();self.add(id='I02',text=b'new',epoch='E2',clock=120)
        self.assertEqual({r['key_epoch'] for r in self.reg.audit_candidates(150)},{'E1','E2'})
    def test_compromised_downgrade(self):
        self.add();self.reg.compromise('E1')
        self.assertEqual(self.reg.exact_public(b'author text',150)['record']['evidence_status'],'KEY_COMPROMISED')
    def test_identical_unsigned_content_ambiguous(self):
        self.add();self.add(id='I02',recipient='C')
        self.assertEqual(self.reg.exact_public(b'author text',150)['status'],'AMBIGUOUS')
    def test_unknown_text_reject(self):
        self.add();self.assertEqual(self.reg.exact_public(b'unseen',150)['status'],'REJECT')
    def test_unregistered_id(self):
        self.assertEqual(self.reg.associate_ids(['UNISSUED'],150)['status'],'UNKNOWN_ISSUE')
    def test_candidate_dedup(self):
        self.add();self.assertEqual(self.reg.associate_ids(['I01','I01'],150)['status'],'ASSOCIATED')
    def test_retention_expires_not_reclassified(self):
        self.add();self.assertEqual(self.reg.exact_public(b'author text',901)['status'],'REJECT')
    def test_clock_and_extra_schema(self):
        r=self.row();r['issued_at']=20.0
        with self.assertRaises(ValueError):canonical(r)
        r=self.row();r['true_recipient']='C'
        with self.assertRaises(ValueError):canonical(r)

if __name__=='__main__':unittest.main()
